import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

import requests
from tabulate import tabulate
import platform

# Assuming these exist based on your snippet
from utils.champion_names import load_champ_name_map
from utils.dd_champ_names import fuzzy_dd_lookup, load_ddragon_champion_map

# --- SOURCE 1: MERAKI (High Quality, Slower Updates) ---
def fetch_meraki_champion(champ_key: str):
    url = f"https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions/{champ_key}.json"
    try:
        r = requests.get(url, timeout=2) # Short timeout so we don't hang if site is slow
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def parse_meraki(meraki_data):
    if not meraki_data or "abilities" not in meraki_data:
        return []

    rows = []
    order = ["P", "Q", "W", "E", "R"]
    for key in order:
        spell_list = meraki_data["abilities"].get(key, [])
        for spell in spell_list:
            name = spell.get("name", "Unknown")

            # Cooldowns
            cd_values = []
            if spell.get("cooldown") and "modifiers" in spell["cooldown"]:
                for mod in spell["cooldown"]["modifiers"]:
                    if "values" in mod:
                        cd_values = mod["values"]
                        break

            # Recharge
            rec_values = []
            rec_obj = spell.get("rechargeRate")
            if isinstance(rec_obj, list): rec_values = rec_obj
            elif isinstance(rec_obj, dict) and "modifiers" in rec_obj:
                for mod in rec_obj["modifiers"]:
                    if "values" in mod:
                        rec_values = mod["values"]
                        break
            elif isinstance(rec_obj, (int, float)): rec_values = [rec_obj]

            rows.append({
                "source": "Meraki",
                "key": key,
                "name": name,
                "cooldowns": cd_values,
                "recharge": rec_values
            })
    return rows

# --- SOURCE 2: CDRAGON + DDRAGON (Raw Data, Always Up-to-Date) ---
def fetch_latest_patch():
    return requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]

def fetch_ddragon_details(slug: str, patch: str):
    url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion/{slug}.json"
    r = requests.get(url)
    if r.status_code != 200: return None
    return r.json()["data"][slug]

def fetch_cdragon_data(champ_id: int):
    url = f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champions/{champ_id}.json"
    r = requests.get(url)
    if r.status_code != 200: return None
    return r.json()

def parse_cdragon(dd_data, cd_data):
    out = []

    # 1. Passive (from DDragon for name)
    out.append({
        "source": "CDragon",
        "key": "P",
        "name": dd_data["passive"]["name"],
        "cooldowns": [],
        "recharge": []
    })

    # 2. Spells (Q-R)
    # CDragon spells list: 0=Q, 1=W, 2=E, 3=R
    keys = ["Q", "W", "E", "R"]
    cd_spells = cd_data["spells"]
    dd_spells = dd_data["spells"]

    for i in range(min(len(cd_spells), 4)):
        s_cd = cd_spells[i]

        # Name Fallback
        name = dd_spells[i]["name"] if i < len(dd_spells) else s_cd.get("name", "Unknown")

        # Cooldowns
        raw_cds = s_cd.get("cooldownCoefficients", [])

        # Ammo
        recharge = []
        ammo_data = s_cd.get("ammo")
        if ammo_data:
            recharge = ammo_data.get("ammoRechargeTime", [])

        out.append({
            "source": "CDragon",
            "key": keys[i] if i < 4 else "?",
            "name": name,
            "cooldowns": raw_cds,
            "recharge": recharge
        })
    return out

def clear():
    if platform.system() == "Windows": os.system("cls")
    else: os.system("clear")
# --- MAIN LOGIC ---
def main():
    patch = fetch_latest_patch()
    name_map = load_ddragon_champion_map(patch)

    # Helper function to format seconds into "Xm Ys"
    def fmt_time(t):
        if t < 60:
            # round to 1 decimal place, remove trailing .0
            return str(round(t, 1)).rstrip('0').rstrip('.')
        if(t==60):
            return "1m"

        m = int(t // 60)
        s = round(t % 60, 1)
        if s == int(s): s = int(s) # Clean look for exact seconds
        formatted_output = f"{m}m {s}"
        return formatted_output

    raw_input = input("Enemy champion(s) (ex. 'Vi + Gnar'): ").strip()
    if not raw_input: return

    # Split input by "+" to handle single or botlane (multiple) queries
    queries = [q.strip() for q in raw_input.split('+') if q.strip()]

    for i, query in enumerate(queries):
        # Visual separator between champions
        if i > 0: print("\n" + "="*60)

        # 1. Identify Champion
        champ_slug = fuzzy_dd_lookup(query, name_map)
        # print(f"\nLooking up: {champ_slug}...")

        abilities = []
        source_used = "Unknown"

        # 2. TRY MERAKI FIRST
        meraki_data = fetch_meraki_champion(champ_slug)
        if meraki_data:
            parsed = parse_meraki(meraki_data)
            if parsed:
                abilities = parsed
                source_used = "Meraki Analytics (Wiki)"

        # 3. FALLBACK TO CDRAGON
        if not abilities:
            print(f"(!) Meraki missing data for {champ_slug}. Falling back to Raw Game Files...")

            dd_champ = fetch_ddragon_details(champ_slug, patch)
            if dd_champ:
                champ_key = int(dd_champ["key"])
                cd_champ = fetch_cdragon_data(champ_key)
                if cd_champ:
                    abilities = parse_cdragon(dd_champ, cd_champ)
                    source_used = "Community Dragon (Raw Client)"

        # 4. Display
        if not abilities:
            print(f"Error: Could not find data for {champ_slug} in either source.")
            continue

        # print(f"--- {champ_slug} ---")
        # print the champion's slug bolded
        # print(f"--- \033[1m{champ_slug}\033[0m ---")
        header_text = Text(
            champ_slug,
            style="bold white on black", # Use a strong style to make it pop!
            justify="center"
        )
        header_panel = Panel(header_text, expand=False, padding=(0, 1))
        console = Console()
        console.print(header_panel)

        # Check for Recharge column
        show_recharge = any((a["recharge"] and any(x > 0 for x in a["recharge"])) for a in abilities)
        headers = ["Key", "Ability", "Cooldowns"]
        if show_recharge: headers.append("Recharge")

        rows = []
        for a in abilities:
            # Formatting Cooldowns
            cd_str = "-"
            if a["cooldowns"] and any(x > 0 for x in a["cooldowns"]):
                cd_str = ", ".join(fmt_time(x) for x in a["cooldowns"])

            row = [a["key"], a["name"], cd_str]

            # Formatting Recharge
            if show_recharge:
                rec_str = "-"
                if a["recharge"] and any(x > 0 for x in a["recharge"]):
                    rec_str = ", ".join(fmt_time(x) for x in a["recharge"])
                row.append(rec_str)

            rows.append(row)
        print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
        # print(tabulate(rows, headers=headers))

import os

def wait_for_enter_only(prompt="Press Enter to reset..."):
    """
    Waits for the user to press Enter.
    Any other key press is ignored and not printed to the screen.
    """
    print(prompt, end='', flush=True)

    # Windows Implementation
    if os.name == 'nt':
        import msvcrt
        while True:
            # getch() reads a keypress without printing it to the console
            key = msvcrt.getch()
            # Check for Enter (Carriage Return \r or Newline \n)
            if key in [b'\r', b'\n']:
                break

    # Linux/macOS Implementation
    else:
        import tty
        import termios
        # Get the file descriptor for standard input
        fd = sys.stdin.fileno()
        # Save old terminal settings to restore them later
        old_settings = termios.tcgetattr(fd)
        try:
            # Set terminal to raw mode (no echo, reads char by char)
            tty.setraw(sys.stdin.fileno())
            while True:
                # Read 1 byte
                char = sys.stdin.read(1)
                # Check for Enter (Carriage Return \r or Newline \n)
                if char in ['\r', '\n']:
                    break
        finally:
            # Restore original terminal settings (very important)
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)




if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"\nError: {e}")
        # input("\nPress Enter to restart...")
        wait_for_enter_only("\nPress Enter to restart...")
        clear()



