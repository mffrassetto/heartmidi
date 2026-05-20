from pathlib import Path

def check_app_data():
    app_data = Path("/app/data/f6776065-8ef6-40f5-bf3a-1cd172ed8935.mid")
    print("/app/data file exists on mac filesystem:", app_data.exists())
    if app_data.exists():
        print("Size:", app_data.stat().st_size, "bytes")
    
    app_dir = Path("/app")
    print("/app directory exists on mac:", app_dir.exists())

if __name__ == "__main__":
    check_app_data()
