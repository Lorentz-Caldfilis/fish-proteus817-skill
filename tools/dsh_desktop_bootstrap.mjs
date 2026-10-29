/** Stable desktop loader protocol v1. Implementations use content-addressed URLs.
 * DSH reuses an existing entry's callback on configuration updates, so keep this
 * loader small and load the configured implementation again on every apply.
 */
export const name = 'fish-proteus-desktop-bootstrap-v1';
export const inject = ['tools', 'workingDirectory'];
export async function apply(ctx, config) {
  const implementation = await import(config.implementationModule);
  return implementation.apply(ctx, config);
}
