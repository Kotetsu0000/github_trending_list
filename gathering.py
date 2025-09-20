import aiohttp
import argparse
import asyncio
import json
import os
import requests
from typing import List, Dict
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

def get_trending_languages() -> List[str]:
    """
    GitHub Trendingページからプログラミング言語のリストを取得します。
    URLで使用できる形式（例: 'python', 'rust'）で返されます。

    Returns:
        プログラミング言語の文字列リスト。
        取得に失敗した場合は空のリストを返します。
    """
    url = "https://github.com/trending"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    
    languages = []
    # Languageドロップダウンメニューのコンテナを探す
    language_menu = soup.find('details', id='select-menu-language')
    if not language_menu:
        return []
        
    # 'data-filter-list' 属性を持つリスト本体を探す
    language_list_container = language_menu.find('div', attrs={'data-filter-list': True})
    if not language_list_container:
        return []

    # 各言語のリンクから言語名を抽出
    for lang_link in language_list_container.find_all('a'):
        href = lang_link['href']
        # URLのパス部分から言語名を取得 (例: /trending/python?since=daily -> python)
        path = urlparse(href).path
        parts = path.split('/')
        if len(parts) > 2:
            language_slug = parts[2]
            languages.append(language_slug)
            
    return languages

async def get_github_trending_repositories_async(
    session: aiohttp.ClientSession, 
    url: str,
    semaphore: asyncio.Semaphore  # <- 追加
) -> List[Dict]:
    """
    aiohttpを使って非同期でGitHub TrendingのURLからリポジトリ情報をスクレイピングし、
    辞書のリストとして返します。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ja;q=0.8", # <- ヘッダーを少し追加
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    }
    
    # セマフォを使って同時実行数を制御
    async with semaphore:
        print(f"Fetching {url}...")
        try:
            # async with で非同期にGETリクエストを送信
            async with session.get(url, headers=headers, timeout=10) as response:
                # ステータスコードが200番台でない場合は例外を発生させる
                response.raise_for_status()
                # await でレスポンスのHTMLを非同期に取得
                html = await response.text()
        except Exception as e:
            print(f"Error fetching URL {url}: {e}")
            return []
        
        # 1秒待機してサーバーへの負荷を軽減
        await asyncio.sleep(1)

    # BeautifulSoupでのHTML解析はCPUバウンドな同期処理なので、awaitは不要
    soup = BeautifulSoup(html, 'html.parser')
    
    repo_articles = soup.find_all('article', class_='Box-row')
    
    trending_repos = []
    
    # (以降の解析ロジックは変更なし)
    for article in repo_articles:
        try:
            repo_link_tag = article.find('h2', class_='h3').find('a')
            repo_name = repo_link_tag.text.replace('\n', '').replace(' ', '')
            repo_link = "https://github.com" + repo_link_tag['href']
            description_tag = article.find('p', class_='col-9')
            description = description_tag.text.strip() if description_tag else "No description provided."
            language_tag = article.find('span', itemprop='programmingLanguage')
            language = language_tag.text.strip() if language_tag else "N/A"
            base_repo_path = repo_link_tag['href']
            star_tag = article.select_one(f'a[href="{base_repo_path}/stargazers"]')
            fork_tag = article.select_one(f'a[href="{base_repo_path}/forks"]')
            stars = int(star_tag.text.strip().replace(',', '')) if star_tag else 0
            forks = int(fork_tag.text.strip().replace(',', '')) if fork_tag else 0
            date_range_stars_tag = article.find('span', class_='d-inline-block float-sm-right')
            if date_range_stars_tag:
                stars_text = date_range_stars_tag.text.strip().split(' ')[0]
                date_range_stars = int(stars_text.replace(',', ''))
            else:
                date_range_stars = 0
            trending_repos.append({
                'repository_name': repo_name,
                'repository_url': repo_link,
                'description': description,
                'language': language,
                'star': stars,
                'fork': forks,
                'date_range_stars': date_range_stars,
            })
        except (AttributeError, ValueError) as e:
            print(f"Could not parse a repository on {url}: {e}")
            continue
        
    return trending_repos

def save_dict(path:str, data:dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_list(filepath: str, data: list[str]) -> bool:
    """
    文字列のリストをテキストファイルに一行ずつ保存します。

    Args:
        filepath (str): 保存先のファイルパス。
        data (list[str]): 保存する文字列のリスト。

    Returns:
        bool: 保存に成功した場合はTrue、失敗した場合はFalse。
    """
    try:
        # 'w'モードでファイルを開き、エンコーディングを'utf-8'に指定
        with open(filepath, 'w', encoding='utf-8') as f:
            # 各要素の末尾に改行を加えて書き込む
            for item in data:
                f.write(item + '\n')
        return True
    except IOError as e:
        print(f"ファイルの保存中にエラーが発生しました: {e}")
        return False

def load_list(filepath: str) -> list[str] | None:
    """
    テキストファイルからデータを一行ずつ読み込み、文字列のリストとして返却します。

    Args:
        filepath (str): 読み込むファイルのパス。

    Returns:
        list[str] | None: 読み込んだ文字列のリスト。ファイルが存在しない場合はNone。
    """
    # ファイルが存在しない場合はNoneを返す
    if not os.path.exists(filepath):
        print(f"エラー: ファイルが見つかりません - {filepath}")
        return None
        
    try:
        # 'r'モードでファイルを開き、エンコーディングを'utf-8'に指定
        with open(filepath, 'r', encoding='utf-8') as f:
            # readlines()で全行をリストとして取得し、
            # リスト内包表記で各行の末尾の改行文字を削除する
            lines = [line.strip() for line in f.readlines()]
        return lines
    except IOError as e:
        print(f"ファイルの読み込み中にエラーが発生しました: {e}")
        return None

async def main(since:str, spoken_language_code:str):
    default = since=='daily' and spoken_language_code=='all'
    output_file = f'./temp/{since}-{spoken_language_code}.json'
    output_lang_file = f'./temp/lang_list.txt'

    if default:
        languages = ['all'] + get_trending_languages()
    else:
        languages = load_list('./temp/lang_list.txt')

    if spoken_language_code=='all':
        urls = [f"https://github.com/trending?since={since}"] + [f"https://github.com/trending/{i}?since={since}" for i in languages if i != 'all']
    else:
        urls = [f"https://github.com/trending?since={since}"] + [f"https://github.com/trending/{i}?since={since}&spoken_language_code={spoken_language_code}" for i in languages if i != 'all']

    semaphore = asyncio.Semaphore(5)

    async with aiohttp.ClientSession() as session:
        tasks = [get_github_trending_repositories_async(session, url, semaphore) for url in urls]
        print("task start")
        results = await asyncio.gather(*tasks)
        print("task end")

    output = {}
    langs = []
    for result, language in zip(results, languages):
        if len(result) == 0:
            continue
        for repo in result:
            if repo['repository_name'] in output.keys():
                output[repo['repository_name']]['published'].append({'language':language, 'spoken_language_code': spoken_language_code, 'since': since})
            else:
                output[repo['repository_name']] = repo
                output[repo['repository_name']]['published'] = [{'language':language, 'spoken_language_code': spoken_language_code, 'since': since}]
        if language != "all":
            langs.append(language)
    
    if not os.path.exists(os.path.dirname(output_file)):
        os.mkdir(os.path.dirname(output_file))

    save_dict(output_file, list(output.values()))
    save_list(output_lang_file, langs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', default='daily')
    parser.add_argument('--spoken_language_code', default='all')
    args = parser.parse_args()
    asyncio.run(main(args.since, args.spoken_language_code))
# uv run gathering.py --since daily --spoken_language_code en