/**
 * 通过点分隔的路径获取嵌套对象的值
 * @param obj 源对象
 * @param path 点分隔的路径字符串，如 "model_paths.qwen_image.dit_path"
 * @param defaultValue 默认值，当路径不存在时返回
 * @returns 路径对应的值或默认值
 *
 * @example
 * const obj = { a: { b: { c: 123 } } };
 * getNestedValue(obj, 'a.b.c'); // 123
 * getNestedValue(obj, 'a.b.d', 'default'); // 'default'
 */
export function getNestedValue<T = any>(
  obj: any,
  path: string,
  defaultValue?: T
): T {
  const value = path.split('.').reduce((o, k) => o?.[k], obj);
  return value !== undefined ? value : (defaultValue as T);
}

/**
 * 通过点分隔的路径设置嵌套对象的值（不可变方式）
 * @param obj 源对象
 * @param path 点分隔的路径字符串，如 "model_paths.qwen_image.dit_path"
 * @param value 要设置的值
 * @returns 新的对象（不修改原对象）
 *
 * @example
 * const obj = { a: { b: { c: 1 } } };
 * const newObj = setNestedValue(obj, 'a.b.c', 2);
 * // obj.a.b.c 仍然是 1
 * // newObj.a.b.c 是 2
 */
export function setNestedValue<T = any>(
  obj: T,
  path: string,
  value: any
): T {
  const keys = path.split('.');
  const newObj = structuredClone(obj); // 深拷贝，避免修改原对象

  let current: any = newObj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    // 如果路径不存在，创建空对象
    if (!current[key] || typeof current[key] !== 'object') {
      current[key] = {};
    }
    current = current[key];
  }

  current[keys[keys.length - 1]] = value;
  return newObj;
}

/**
 * 通过点分隔的路径删除嵌套对象的属性（不可变方式）
 * @param obj 源对象
 * @param path 点分隔的路径字符串
 * @returns 新的对象（不修改原对象）
 *
 * @example
 * const obj = { a: { b: { c: 1, d: 2 } } };
 * const newObj = deleteNestedValue(obj, 'a.b.c');
 * // newObj.a.b 只有 d: 2
 */
export function deleteNestedValue<T = any>(
  obj: T,
  path: string
): T {
  const keys = path.split('.');
  const newObj = structuredClone(obj);

  let current: any = newObj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    if (!current[key]) {
      return newObj; // 路径不存在，直接返回
    }
    current = current[key];
  }

  delete current[keys[keys.length - 1]];
  return newObj;
}

/**
 * 检查嵌套路径是否存在
 * @param obj 源对象
 * @param path 点分隔的路径字符串
 * @returns 路径是否存在
 *
 * @example
 * const obj = { a: { b: { c: 1 } } };
 * hasNestedPath(obj, 'a.b.c'); // true
 * hasNestedPath(obj, 'a.b.d'); // false
 */
export function hasNestedPath(obj: any, path: string): boolean {
  const keys = path.split('.');
  let current = obj;

  for (const key of keys) {
    if (current?.[key] === undefined) {
      return false;
    }
    current = current[key];
  }

  return true;
}
