import aiohttp
import asyncio
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import urlparse, parse_qs

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

def get_trending_spoken_languages() -> List[str]:
    """
    GitHub TrendingページからSpoken Languageのリストを取得します。
    URLのクエリパラメータで使用できるコード（例: 'en', 'ja'）で返されます。

    Returns:
        Spoken Languageコードの文字列リスト。
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
    
    spoken_languages = []
    # Spoken Languageドロップダウンメニューのコンテナを探す
    spoken_language_menu = soup.find('details', id='select-menu-spoken-language')
    if not spoken_language_menu:
        return []

    # 各Spoken Languageのリンクから言語コードを抽出
    for lang_link in spoken_language_menu.find_all('a'):
        href = lang_link['href']
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        # 'spoken_language_code' パラメータの値を取得
        lang_code = query_params.get('spoken_language_code', [None])[0]
        if lang_code:
            spoken_languages.append(lang_code)

    return spoken_languages

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

async def main():
    all_langs = get_trending_languages()
    urls = ["https://github.com/trending/" + i for i in all_langs]

    semaphore = asyncio.Semaphore(5)
    
    langs = []
    async with aiohttp.ClientSession() as session:
        # 各URLに対する非同期タスク(コルーチン)のリストを作成
        tasks = [get_github_trending_repositories_async(session, url, semaphore) for url in urls]
        print("task start")
        
        # asyncio.gatherで全てのタスクを並列に実行し、結果を待つ
        # resultsには各タスクの戻り値(リポジトリのリスト)が格納される
        results = await asyncio.gather(*tasks)

        print("task end")
        for result, lang in zip(results, all_langs):
            if len(result) != 0:
                langs.append(lang)

    print(langs)


if __name__ == "__main__":
    asyncio.run(main())
