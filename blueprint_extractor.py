import time
import os
import re
import csv
import sys
import msvcrt
from datetime import datetime, timezone

# Standard SC game log path
LIVE_PATH = "C:\\Program Files\\Roberts Space Industries\\StarCitizen\\LIVE"
LOG_PATH = LIVE_PATH + "\\Game.log"
BACKUP_LOG_PATH = LIVE_PATH + "\\logbackups"
CSV_FILE = "blueprints.csv"
PATTERN = re.compile('<([^>]+)>.*Received Blueprint:\\s*(.*?):\\s*"')

def load_existing_blueprints():
    blueprints = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                if not row: continue
                if idx == 0 and row[0].lower() == 'blueprint name':
                    continue
                blueprints.add(row[0])
    return blueprints

def append_to_csv(blueprint_name, timestamp):
    write_header = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(['Blueprint Name', 'Timestamp'])
        writer.writerow([blueprint_name, timestamp])

def get_file_id(path):
    try:
        return os.stat(path).st_dev, os.stat(path).st_ino
    except FileNotFoundError:
        return None

def time_ago(timestamp_str):
    if not timestamp_str:
        return ""
    try:
        dt = datetime.strptime(timestamp_str[:19], "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt
        minutes = int(diff.total_seconds() / 60)
        
        if minutes < 0:
            return "just now"
        elif minutes < 60:
            return f"{minutes} min ago" if minutes != 1 else "1 min ago"
        elif minutes < 1440:
            hours = minutes // 60
            return f"{hours} hr ago" if hours != 1 else "1 hr ago"
        else:
            days = minutes // 1440
            return f"{days} days ago" if days != 1 else "1 day ago"
    except Exception:
        return timestamp_str

def print_last_10_blueprints():
    if not os.path.exists(CSV_FILE):
        return
    rows = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if not row: continue
            if idx == 0 and row[0].lower() == 'blueprint name':
                continue
            rows.append(row)
    
    last_10 = rows[-10:]
    if not last_10:
        return
        
    print("\n" + "="*80)
    print(f"{'ACQUIRED':<20} | {'BLUEPRINT NAME'}")
    print("-" * 80)
    for row in last_10:
        name = row[0]
        timestamp = row[1] if len(row) > 1 else ""
        acquired_str = time_ago(timestamp)
        print(f"{acquired_str:<20} | {name}")
    print("="*80 + "\n")

def scan_backups():
    backup_dir = BACKUP_LOG_PATH
    if not os.path.exists(backup_dir):
        print(f"Backup directory not found: {backup_dir}")
        return

    known_blueprints = load_existing_blueprints()
    print(f"Scanning backups in {backup_dir}...")
    
    files = sorted([f for f in os.listdir(backup_dir) if f.endswith(".log")])
    if not files:
        print("No log backups found.")
        return

    cutoff_date = datetime(2026, 3, 24).timestamp()

    for filename in files:
        filepath = os.path.join(backup_dir, filename)
        if os.path.getmtime(filepath) < cutoff_date:
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = PATTERN.search(line)
                    if match:
                        timestamp = match.group(1).strip()
                        bp = match.group(2).strip()
                        if bp not in known_blueprints:
                            known_blueprints.add(bp)
                            append_to_csv(bp, timestamp)
                            print(f"[{timestamp}] New blueprint acquired from backup {filename}: {bp}")
        except Exception as e:
            print(f"Error reading {filename}: {e}")

def tail_log(log_file):
    print(f"Monitoring log file: {log_file}")
    
    # Wait for the file to exist before starting
    while not os.path.exists(log_file):
        print(f"Waiting for {log_file} to be created...", end='\r')
        time.sleep(1)
    
    known_blueprints = load_existing_blueprints()
    print(f"\nLoaded {len(known_blueprints)} known blueprints. Showing last 10.")
    
    f = open(log_file, 'r', encoding='utf-8', errors='replace')
    file_id = get_file_id(log_file)
    
    print_last_10_blueprints()
    print("Game.log processing started. Press Escape or Ctrl+C to exit. Waiting for new acquisitions ...")
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b'\x1b':
            print("\nEscape key pressed. Stopping blueprint logger.")
            break

        line = f.readline()
        if not line:
            # Reached end of file. Check if file was rotated/recreated.
            current_id = get_file_id(log_file)
            if current_id and current_id != file_id:
                print(f"\n{log_file} was recreated/rotated. Reopening...")
                f.close()
                f = open(log_file, 'r', encoding='utf-8', errors='replace')
                file_id = current_id
                continue
            
            time.sleep(0.5)
            continue
            
        match = PATTERN.search(line)
        if match:
            timestamp = match.group(1).strip()
            bp = match.group(2).strip()
            if bp not in known_blueprints:
                known_blueprints.add(bp)
                append_to_csv(bp, timestamp)
                print(f"[{timestamp}] New blueprint acquired and logged: {bp}")

if __name__ == "__main__":
    log_file = LOG_PATH
    if len(sys.argv) > 1:
        log_file = sys.argv[1]

    if log_file == LOG_PATH and not os.path.exists(LOG_PATH):
        print("Live log not found")
        sys.exit(1)

    while True:
        choice = input("Would you like to scan older log backups for blueprints? (y/n): ").strip().lower()
        if choice in ('y', 'yes'):
            scan_backups()
            break
        elif choice in ('n', 'no'):
            break
        else:
            print("Please answer 'y' or 'n'.")

    try:
        tail_log(log_file)
    except KeyboardInterrupt:
        print("\nStopping blueprint logger.")
