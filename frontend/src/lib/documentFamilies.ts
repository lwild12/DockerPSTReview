// Groups a flat, already-ordered list of documents so each attachment
// renders directly under its parent email, regardless of where the API's
// own sort (e.g. by sent_at, which attachments don't have) placed it.

export interface FamilyRow<T> {
  item: T;
  isChild: boolean;
  childCount: number;
}

export function groupIntoFamilies<T>(
  items: T[],
  getId: (item: T) => string,
  getParentId: (item: T) => string | null,
): FamilyRow<T>[] {
  const ids = new Set(items.map(getId));
  const children = childrenByParent(items, getParentId);

  const result: FamilyRow<T>[] = [];
  for (const item of items) {
    const parentId = getParentId(item);
    if (parentId && ids.has(parentId)) continue; // rendered under its parent below
    const kids = children.get(getId(item)) ?? [];
    result.push({ item, isChild: false, childCount: kids.length });
    for (const child of kids) {
      result.push({ item: child, isChild: true, childCount: 0 });
    }
  }
  return result;
}

export function childrenByParent<T>(
  items: T[],
  getParentId: (item: T) => string | null,
): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const parentId = getParentId(item);
    if (!parentId) continue;
    const list = map.get(parentId) ?? [];
    list.push(item);
    map.set(parentId, list);
  }
  return map;
}
