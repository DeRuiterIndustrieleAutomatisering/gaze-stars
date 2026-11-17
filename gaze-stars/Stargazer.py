#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @Author  :   Arthals
# @File    :   Stargazer.py
# @Time    :   2025/01/22 16:16:16
# @Contact :   zhuozhiyongde@126.com
# @Software:   Visual Studio Code

import html
import json
import os
import re
import requests


class Stargazer:
    def __init__(self):
        self.username = os.getenv("GITHUB_USERNAME")
        self.token = os.getenv("GITHUB_TOKEN")
        self.template = os.getenv("TEMPLATE_PATH", "template/template.md")
        self.output = os.getenv("OUTPUT_PATH", "README.md")
        self.sort_by = os.getenv("SORT_BY", "stars")
        self.star_lists = []
        self.star_list_repos = {}
        self.data = {}

    def get_all_starred(self):
        url = f"https://api.github.com/users/{self.username}/starred?per_page=100"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Stargazer",
        }
        all_repos = {}
        while url:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            for repo in response.json():
                all_repos[repo["full_name"]] = {
                    "html_url": repo["html_url"],
                    "description": repo["description"] or "",
                    "listed": False,
                    "stars": repo["stargazers_count"],
                }
            url = response.links.get("next", {}).get("url")
        self.data = all_repos
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(all_repos, f, indent=4, ensure_ascii=False)
        return all_repos

    def get_lists(self):
        url = f"https://github.com/{self.username}?tab=stars"
        response = requests.get(url, timeout=30, headers={"User-Agent": "Stargazer"})
        response.raise_for_status()

        list_map = {}
        pattern = rf'href="(/stars/{re.escape(self.username)}/lists/[^"?#]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)

        for href, name_html in matches:
            list_slug = href.rstrip("/").split("/")[-1]
            cleaned = re.sub(r"<[^>]+>", "", name_html)
            cleaned = html.unescape(cleaned).strip()
            list_map[list_slug] = cleaned or list_slug.replace("-", " ").title()

        self.star_lists = [(slug, name) for slug, name in list_map.items()]
        return self.star_lists

    def get_list_repos(self, list_name):
        url = "https://github.com/stars/{username}/lists/{list_name}?page={page}"
        page = 1
        self.star_list_repos.setdefault(list_name, [])
        seen = set()

        while True:
            current_url = url.format(
                username=self.username, list_name=list_name, page=page
            )
            response = requests.get(
                current_url,
                timeout=30,
                headers={"User-Agent": "Stargazer"},
            )
            response.raise_for_status()

            matches = re.findall(
                r'href="/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"',
                response.text,
            )

            if not matches:
                break

            new_entries = []
            for owner, repo in matches:
                if owner == self.username:
                    continue
                candidate = f"{owner}/{repo}"
                if candidate in seen:
                    continue
                seen.add(candidate)
                new_entries.append((owner, repo))

            if not new_entries:
                break

            self.star_list_repos[list_name].extend(new_entries)
            page += 1

        return self.star_list_repos[list_name]

    def get_all_repos(self):
        for list_url, _ in self.star_lists:
            self.get_list_repos(list_url)
        return self.star_list_repos

    @staticmethod
    def format_repo_line(name, repo):
        description = " ".join((repo["description"] or "").split())
        if len(description) > 140:
            description = description[:137].rstrip() + "..."

        line = f"- [{name}](https://github.com/{name})"
        if description:
            line += f" — {description}"
        line += f" (stars: {repo['stars']:,})"
        return line

    def generate_readme(self):
        text = ""

        for list_url, list_name in self.star_lists:
            repos = [
                (f"{user}/{repo}", self.data[f"{user}/{repo}"])
                for user, repo in self.star_list_repos.get(list_url, [])
                if f"{user}/{repo}" in self.data
            ]
            if self.sort_by == "stars":
                sorted_repos = sorted(repos, key=lambda x: x[1]["stars"], reverse=True)
            else:
                sorted_repos = repos[::-1]

            text += f"## {list_name}\n\n"
            if not sorted_repos:
                text += "_No repositories in this list._\n\n"
            else:
                for key, repo in sorted_repos:
                    repo["listed"] = True
                    text += self.format_repo_line(key, repo) + "\n\n"
            text += "\n"

        if self.sort_by == "stars":
            unlisted = sorted(
                [key for key in self.data if not self.data[key]["listed"]],
                key=lambda x: self.data[x]["stars"],
                reverse=True,
            )
        else:
            unlisted = [key for key in self.data if not self.data[key]["listed"]]
            unlisted = unlisted[::-1]

        text += "## Repo-x\n\n"
        if not unlisted:
            text += "_All repositories are classified._\n\n"
        else:
            for k in unlisted:
                text += self.format_repo_line(k, self.data[k]) + "\n\n"

        text += "\n"

        with open(self.template, "r", encoding="utf-8") as f:
            template = f.read()

        with open(self.output, "w", encoding="utf-8") as f:
            f.write(template.replace("[[GENERATE HERE]]", text.strip()))


if __name__ == "__main__":
    stargazer = Stargazer()
    stargazer.get_all_starred()
    stargazer.get_lists()
    stargazer.get_all_repos()
    stargazer.generate_readme()
