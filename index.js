import { cpSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, realpathSync, renameSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const bundledSkins = fileURLToPath(new URL("./skins/", import.meta.url));

export const name = "piora-themes";

function userSkinsDir(env = process.env) {
  const override = env.DSH_SKINS_HOME?.trim() || env.DSH_SKINS_DIR?.trim();
  const harnessHome = env.DSH_HOME?.trim() || join(homedir(), ".dsh");
  return resolve(override || join(harnessHome, "skins"));
}

function entryExists(path) {
  try {
    lstatSync(path);
    return true;
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

export function installSkins(target = userSkinsDir()) {
  mkdirSync(target, { recursive: true });
  const root = realpathSync(target);
  const installed = [];
  const existing = [];

  for (const entry of readdirSync(bundledSkins, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const id = entry.name;
    const destination = join(root, id);
    if (entryExists(destination)) {
      existing.push(id);
      continue;
    }

    // Skin Center scans every directory in the catalog root.
    const parent = dirname(root);
    const stage = mkdtempSync(join(parent, ".piora-themes-"));
    try {
      cpSync(join(bundledSkins, id), stage, { recursive: true });
      try {
        renameSync(stage, destination);
        installed.push(id);
      } catch (error) {
        if (!entryExists(destination)) throw error;
        existing.push(id);
      }
    } finally {
      if (dirname(stage) === parent && basename(stage).startsWith(".piora-themes-")) {
        rmSync(stage, { recursive: true, force: true });
      }
    }
  }

  return { installed, existing };
}

export function apply() {
  installSkins();
}
