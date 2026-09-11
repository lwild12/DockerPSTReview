#!/usr/bin/env python3
"""Standalone diagnostic: run against a real PST to see why some
inline-looking attachments aren't being recognized as inline by
_pypff_attachments (PR_ATTACH_CONTENT_ID / PR_ATTACHMENT_HIDDEN detection).

Prints only structural info -- counts, MAPI property tags, filenames,
sizes -- never message subjects, senders, or body content. Safe to paste
the output back for diagnosis.

Usage:
    python diagnose_inline_attachments.py /path/to/file.pst [--max-examples N]
"""

from __future__ import annotations

import argparse
import sys

import pypff

_PR_ATTACH_CONTENT_ID = 0x3712
_PR_ATTACHMENT_HIDDEN = 0x7FFE
_PR_ATTACH_LONG_FILENAME = 0x3707
_PR_ATTACH_FILENAME = 0x3704
_PR_ATTACH_MIME_TAG = 0x370E
_PR_ATTACH_NUM = 0x0E21
_PR_ATTACH_METHOD = 0x3705


def find_record_entry(item, tag: int):
    try:
        for i in range(item.get_number_of_record_sets()):
            record_set = item.get_record_set(i)
            for j in range(record_set.get_number_of_entries()):
                entry = record_set.get_entry(j)
                if entry.get_entry_type() == tag:
                    return entry
    except Exception:
        return None
    return None


def all_tags(item) -> list[str]:
    tags = []
    try:
        for i in range(item.get_number_of_record_sets()):
            record_set = item.get_record_set(i)
            for j in range(record_set.get_number_of_entries()):
                entry = record_set.get_entry(j)
                tags.append(hex(entry.get_entry_type()))
    except Exception as exc:
        tags.append(f"ERROR:{exc}")
    return tags


def get_string(item, tag: int) -> str:
    entry = find_record_entry(item, tag)
    if entry is None:
        return ""
    try:
        return entry.get_data_as_string() or ""
    except Exception:
        return ""


def get_bool(item, tag: int) -> bool:
    entry = find_record_entry(item, tag)
    if entry is None:
        return False
    try:
        return bool(entry.get_data_as_boolean())
    except Exception:
        return False


def get_int(item, tag: int):
    entry = find_record_entry(item, tag)
    if entry is None:
        return None
    for getter in ("get_data_as_integer", "get_data_as_long"):
        fn = getattr(entry, getter, None)
        if fn is None:
            continue
        try:
            return fn()
        except Exception:
            pass
    return None


def walk_folder(folder, stats, examples, max_examples, rtf_examples, max_rtf_examples):
    for message in folder.sub_messages:
        try:
            att_count = message.get_number_of_attachments()
        except Exception:
            att_count = 0
        if att_count == 0:
            continue

        message_neither_count = 0
        for j in range(att_count):
            try:
                att = message.get_attachment(j)
            except Exception:
                continue

            content_id = get_string(att, _PR_ATTACH_CONTENT_ID).strip().strip("<>")
            hidden = get_bool(att, _PR_ATTACHMENT_HIDDEN)
            mime_type = get_string(att, _PR_ATTACH_MIME_TAG)
            filename = get_string(att, _PR_ATTACH_LONG_FILENAME) or get_string(
                att, _PR_ATTACH_FILENAME
            )
            attach_num = get_int(att, _PR_ATTACH_NUM)
            attach_method = get_int(att, _PR_ATTACH_METHOD)

            stats["total"] += 1
            if content_id:
                stats["with_content_id"] += 1
            elif hidden:
                stats["hidden_no_content_id"] += 1
            else:
                stats["neither"] += 1
                message_neither_count += 1
                if len(examples) < max_examples:
                    try:
                        size = att.get_size()
                    except Exception:
                        size = None
                    examples.append(
                        {
                            "filename": filename,
                            "mime_type": mime_type,
                            "size": size,
                            "attach_num": attach_num,
                            "attach_method": attach_method,
                            "tags": all_tags(att),
                        }
                    )

        # If this message had attachments with neither signal, grab a
        # snippet of its RTF body around the first \objattph marker (the
        # RTF control word Outlook uses to anchor an embedded object at a
        # specific position -- matched to an attachment via PR_ATTACH_NUM,
        # not Content-ID). Confirms/refutes the RTF-anchoring theory.
        if message_neither_count > 0 and len(rtf_examples) < max_rtf_examples:
            try:
                rtf = message.get_rtf_body()
            except Exception:
                rtf = None
            if rtf:
                if isinstance(rtf, bytes):
                    rtf_text = rtf.decode("latin-1", errors="replace")
                else:
                    rtf_text = str(rtf)
                idx = rtf_text.find("objattph")
                rtf_examples.append(
                    {
                        "has_objattph": idx != -1,
                        "objattph_count": rtf_text.count("objattph"),
                        "snippet": rtf_text[max(0, idx - 40) : idx + 80] if idx != -1 else "",
                    }
                )

    for sub_folder in folder.sub_folders:
        walk_folder(sub_folder, stats, examples, max_examples, rtf_examples, max_rtf_examples)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pst_path")
    parser.add_argument("--max-examples", type=int, default=10)
    parser.add_argument("--max-rtf-examples", type=int, default=5)
    args = parser.parse_args()

    pst = pypff.file()
    pst.open(args.pst_path)
    root = pst.get_root_folder()

    stats = {"total": 0, "with_content_id": 0, "hidden_no_content_id": 0, "neither": 0}
    examples: list[dict] = []
    rtf_examples: list[dict] = []

    walk_folder(root, stats, examples, args.max_examples, rtf_examples, args.max_rtf_examples)
    pst.close()

    print("=== Attachment classification counts ===")
    for key, value in stats.items():
        print(f"{key}: {value}")

    print()
    print(f"=== Up to {args.max_examples} example attachments with neither signal ===")
    for ex in examples:
        print(ex)

    print()
    print(f"=== Up to {args.max_rtf_examples} RTF-body \\objattph snippets ===")
    for ex in rtf_examples:
        print(ex)

    return 0


if __name__ == "__main__":
    sys.exit(main())
