import json
import os
from typing import List, Dict

from bs4 import BeautifulSoup
import requests

def get_github_trending_repositories(url: str) -> List[Dict]:
    """
    指定されたGitHub TrendingのURLからリポジトリ情報をスクレイピングし、
    辞書のリストとして返します。

    Args:
        url: GitHub TrendingページのURL。

    Returns:
        各リポジトリの情報を格納した辞書のリスト。
        取得に失敗した場合は空のリストを返します。
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # トレンドリポジトリは 'article' タグの 'Box-row' クラス内に格納されている
    repo_articles = soup.find_all('article', class_='Box-row')
    
    trending_repos = []
    
    for article in repo_articles:
        # リポジトリ名とリンク
        repo_link_tag = article.find('h2', class_='h3').find('a')
        # テキスト内の不要な空白や改行を削除
        repo_name = repo_link_tag.text.replace('\n', '').replace(' ', '')
        repo_link = "https://github.com" + repo_link_tag['href']

        # Description
        description_tag = article.find('p', class_='col-9')
        description = description_tag.text.strip() if description_tag else "No description provided."

        # 主要な言語
        language_tag = article.find('span', itemprop='programmingLanguage')
        language = language_tag.text.strip() if language_tag else "N/A"

        # Star数とFork数
        # `a` タグを直接指定すると、複数のリンクが含まれるため、より詳細なセレクタを使用
        base_repo_path = repo_link_tag['href']
        star_tag = article.select_one(f'a[href="{base_repo_path}/stargazers"]')
        fork_tag = article.select_one(f'a[href="{base_repo_path}/forks"]')
        
        # 数値からカンマを除去して整数に変換
        stars = int(star_tag.text.strip().replace(',', '')) if star_tag else 0
        forks = int(fork_tag.text.strip().replace(',', '')) if fork_tag else 0

        # Date range stars
        date_range_stars_tag = article.find('span', class_='d-inline-block float-sm-right')
        # "1,234 stars this month" のようなテキストから数値のみを抽出
        if date_range_stars_tag:
            # "stars" という単語で分割し、その前の部分を取得して処理
            stars_text = date_range_stars_tag.text.strip().split(' ')[0]
            date_range_stars = int(stars_text.replace(',', ''))
        else:
            date_range_stars = 0
            
        trending_repos.append({
            'repository_name': repo_name,
            'repository_url': repo_link,
            #'description': description,
            #'language': language,
            #'star': stars,
            #'fork': forks,
            #'date_range_stars': date_range_stars,
        })
        
    return trending_repos

def main():
    folder = 'temp'
    data = get_github_trending_repositories('https://github.com/trending')
    if not os.path.exists(folder):
        os.mkdir(folder)
    sorted_data = sorted(data, key=lambda x: x["repository_name"])
    with open(f'{folder}/data.json', 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
