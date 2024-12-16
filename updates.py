#!/usr/bin/env python3

import datetime
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from webbrowser import open_new_tab

import colorama
import httpx
import prettytable
from tqdm import tqdm


@dataclass
class Mod:
    name: str
    version: str
    url: str
    last_updated: datetime.datetime | None = None
    deprecated: bool = False


def read_mods_list(mod_category: str) -> dict[str, Mod]:
    """Read the README.md file and extract the mods list"""
    with open("README.md", "r") as f:
        lines = f.readlines()

    mods: dict[str, Mod] = {}
    found_mods_table: bool = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(f"### {mod_category}"):  # Found heading
            found_mods_table = True
            i += 4  # Skip the table header
            continue

        if found_mods_table:
            line = lines[i]
            if not line.startswith("|"):  # End of table
                break

            mod_name = (
                line.partition("|")[2]
                .partition("|")[0]
                .partition("[")[2]
                .partition("]")[0]
                .strip()
            )
            mod_url = (
                line.partition("|")[2]
                .partition("|")[0]
                .partition("(")[2]
                .partition(")")[0]
                .strip()
            )
            mod_version = (
                line.partition("|")[2].partition("|")[2].partition("|")[0].strip()
            )
            mods[mod_name] = Mod(mod_name, mod_version, mod_url)

        i += 1

    print(f"Found {len(mods)} {mod_category}")
    return mods


def get_mod_update(mod: Mod) -> Mod | None:
    request_urls = {
        "thunderstore.io": "https://thunderstore.io/api/experimental/package/{namespace}/{name}/",
        "github.com": "https://api.github.com/repos/{owner}/{repo}/releases/latest",
    }

    source = urlparse(mod.url).netloc
    if source not in request_urls:
        print(f"[E] {mod.name} does not have a supported source: {source}")
        return None

    if source == "thunderstore.io":
        try:
            namespace, name = urlparse(mod.url).path.split("/")[-3:-1]
            url = request_urls[source].format(namespace=namespace, name=name)
            response = httpx.get(url)

            _ = response.raise_for_status()
            data = response.json()
            if (
                data["latest"]["version_number"][1:]
                if data["latest"]["version_number"].startswith("v")
                else data["latest"]["version_number"]
            ) != mod.version or data["is_deprecated"]:
                return Mod(
                    mod.name,
                    (
                        data["latest"]["version_number"][1:]
                        if data["latest"]["version_number"].startswith("v")
                        else data["latest"]["version_number"]
                    ),
                    mod.url,
                    datetime.datetime.fromisoformat(data["date_updated"]),
                    data["is_deprecated"],
                )

        except Exception as e:
            print(f"[E] Failed to check for updates for {mod.name}: {e}")
            return None

    elif source == "github.com":
        try:
            owner, repo = urlparse(mod.url).path.split("/")[1:3]
            url = request_urls[source].format(owner=owner, repo=repo)
            response = httpx.get(url)
            _ = response.raise_for_status()
            data = response.json()
            if (
                data["tag_name"][1:]
                if data["tag_name"].startswith("v")
                else data["tag_name"]
            ) != mod.version:
                return Mod(
                    mod.name,
                    (
                        data["tag_name"][1:]
                        if data["tag_name"].startswith("v")
                        else data["tag_name"]
                    ),
                    mod.url,
                    datetime.datetime.fromisoformat(data["published_at"]),
                )

        except Exception as e:
            print(f"[E] Failed to check for updates for {mod.name}: {e}")
            return None

    else:
        print(f"[E] {mod.name} does not have a supported source: {source}")
        return None


def check_for_updates(mod_category: str, mods: dict[str, Mod]) -> dict[str, Mod]:
    """Use thunderstore.io and github.com APIs to check for updates"""
    upgradable_mods: dict[str, Mod] = {}

    for mod in tqdm(mods.values(), desc=mod_category):
        new_mod = get_mod_update(mod)
        if new_mod:
            upgradable_mods[new_mod.name] = new_mod

    return upgradable_mods


def list_all_mods(
    mods_list: dict[str, dict[str, Mod]], upgradable_mods: dict[str, dict[str, Mod]]
) -> None:
    print()

    def create_table(category: str) -> prettytable.PrettyTable:
        table = prettytable.PrettyTable(title=category)

        table.field_names = [
            "Mod",
            "Old Version",
            "New Version",
            "Last Updated",
            "Deprecated",
            # "URL",
        ]
        table.align = "l"

        return table

    for mod_category in mods_list:
        table = create_table(mod_category)

        for mod in mods_list[mod_category].values():
            if mod.name in upgradable_mods[mod_category]:
                table.add_row(
                    [
                        f"{colorama.Fore.CYAN}{mod.name}{colorama.Style.RESET_ALL}",
                        f"{colorama.Fore.YELLOW}{mod.version}{colorama.Style.RESET_ALL}",
                        f"{colorama.Fore.GREEN}{upgradable_mods[mod_category][mod.name].version}{colorama.Style.RESET_ALL}",
                        (
                            upgradable_mods[mod_category][
                                mod.name
                            ].last_updated.strftime("%Y-%m-%d")
                            if upgradable_mods[mod_category][mod.name].last_updated
                            else f"{colorama.Fore.BLACK}N/A{colorama.Style.RESET_ALL}"
                        ),
                        (
                            f"{colorama.Fore.RED}YES{colorama.Style.RESET_ALL}"
                            if upgradable_mods[mod_category][mod.name].deprecated
                            else f"{colorama.Fore.GREEN}NO{colorama.Style.RESET_ALL}"
                        ),
                        # upgradable_mods[mod_category][mod.name].url,
                    ]
                )

            else:
                table.add_row(
                    [
                        mod.name,
                        mod.version,
                        f"{colorama.Fore.BLACK}N/A{colorama.Style.RESET_ALL}",
                        f"{colorama.Fore.BLACK}N/A{colorama.Style.RESET_ALL}",
                        f"{colorama.Fore.BLACK}N/A{colorama.Style.RESET_ALL}",
                        # mod.url,
                    ]
                )

        print(table)


def list_upgradable_mods(
    mods_list: dict[str, dict[str, Mod]], upgradable_mods: dict[str, dict[str, Mod]]
) -> None:
    """Print only the mods with updates available."""

    i = 1
    for mod_category in upgradable_mods:
        for mod in upgradable_mods[mod_category].values():
            print(
                "{i}: {name}{deprecated} {c_yellow}{old_ver}{c_reset} -> {c_green}{new_ver}{c_reset}".format(
                    c_yellow=colorama.Fore.YELLOW,
                    c_green=colorama.Fore.GREEN,
                    c_reset=colorama.Style.RESET_ALL,
                    i=i,
                    name=mod.name,
                    old_ver=mods_list[mod_category][mod.name].version,
                    new_ver=mod.version,
                    deprecated=(
                        f" ({colorama.Fore.RED}Deprecated{colorama.Style.RESET_ALL})"
                        if mod.deprecated
                        else ""
                    ),
                )
            )
            i += 1


def main():
    """Main function"""

    time_start = time.time()

    mods_list: dict[str, dict[str, Mod]] = {
        "Core": read_mods_list("Core"),
        "Quality-of-Life & Visual Mods": read_mods_list(
            "Quality-of-Life & Visual Mods"
        ),
        "Mods that significantly change the gameplay": read_mods_list(
            "Mods that significantly change the gameplay"
        ),
    }
    upgradable_mods: dict[str, dict[str, Mod]] = {}

    for mod_category in mods_list:
        upgradable_mods[mod_category] = check_for_updates(
            mod_category, mods_list[mod_category]
        )

    if "--all" in sys.argv[1:]:
        list_all_mods(mods_list=mods_list, upgradable_mods=upgradable_mods)

    else:
        list_upgradable_mods(mods_list=mods_list, upgradable_mods=upgradable_mods)

    total_mods = sum(len(mods) for mods in mods_list.values())
    total_upgradable_mods = sum(len(mods) for mods in upgradable_mods.values())
    print(
        f"\n{colorama.Fore.YELLOW}{total_upgradable_mods}{colorama.Style.RESET_ALL} out of {total_mods} mods have updates available."
    )
    if "--open" in sys.argv[1:]:
        print("Opening the update URLs in your browser...")
        for mod_category in upgradable_mods:
            for mod in upgradable_mods[mod_category].values():
                _ = open_new_tab(mod.url)

    print(
        f"Finished in {colorama.Fore.GREEN}{time.time() - time_start:.2f}{colorama.Style.RESET_ALL} seconds."
    )


if __name__ == "__main__":
    main()
