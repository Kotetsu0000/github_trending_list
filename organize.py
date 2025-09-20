from datetime import datetime, timezone, timedelta
import glob
import json
import os

def get_json_files():
    temp_dir = "temp"
    # temp直下の *.json を検索
    return [i for i in glob.glob(os.path.join(temp_dir, "*.json")) if i != 'temp/data.json']

def get_jst_time():
    # 現在のUTC時刻
    #utc_now = datetime.now(timezone.utc)
    #utc_str = utc_now.strftime("%Y_%m_%d_%H")

    # 日本時間 (UTC+9)
    jst = timezone(timedelta(hours=9))
    jst_now = datetime.now(jst)
    jst_str = jst_now.strftime("%Y_%m_%d_%H")
    return jst_str

def save_dict(path:str, data:dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_dict(path:str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    output_dir = './data'
    print("JST :", get_jst_time())

    output = {}
    for file_path in get_json_files():
        print(f'Current: {file_path}')
        for repo in load_dict(file_path):
            if repo['repository_name'] in output.keys():
                output[repo['repository_name']]['published'].extend(repo['published'])
            else:
                output[repo['repository_name']] = repo

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    save_dict(f'{output_dir}/latest.json', list(output.values()))
    save_dict(f'{output_dir}/{get_jst_time()}.json', list(output.values()))

if __name__ == "__main__":
    main()
