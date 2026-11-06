import { execFileSync } from "node:child_process";
import path from "node:path";

/** Stop the e2e API container (its database and data are kept). Skipped when reusing a server. */
export default function teardown() {
  if (process.env.E2E_KEEP_SERVERS) return;
  execFileSync("docker", ["compose", "--profile", "e2e", "stop", "api-e2e"], {
    cwd: path.resolve(__dirname, "../.."),
    stdio: "ignore",
  });
}
