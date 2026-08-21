// Keep this test-only seam independent of workspace-hoisted @types/node.
declare module "node:fs" {
  export function readFileSync(
    path: string | URL,
    encoding: "utf8",
  ): string;
}
