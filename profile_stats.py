"""Safe GitHub profile stats loader for the terminal generators."""

from __future__ import annotations

import os
from types import SimpleNamespace

import requests
from gifos.utils import calc_github_rank


QUERY = """
query ProfileStats($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    issues { totalCount }
    pullRequests { totalCount }
    repositoriesContributedTo { totalCount }
    contributionsCollection {
      restrictedContributionsCount
      totalCommitContributions
      totalPullRequestReviewContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def fetch_profile_stats(username: str):
    """Return the fields used by the GIF without the upstream zero-PR bug."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None

    response = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {token}"},
        json={"query": QUERY, "variables": {"login": username}},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0]["message"])

    user = payload["data"]["user"]
    contributions = user["contributionsCollection"]
    commits = (
        contributions["restrictedContributionsCount"]
        + contributions["totalCommitContributions"]
    )
    prs = user["pullRequests"]["totalCount"]
    issues = user["issues"]["totalCount"]
    reviews = contributions["totalPullRequestReviewContributions"]
    followers = user["followers"]["totalCount"]

    stars = 0
    language_sizes: dict[str, int] = {}
    for repo in user["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            language = edge["node"]["name"]
            language_sizes[language] = language_sizes.get(language, 0) + edge["size"]

    language_total = sum(language_sizes.values())
    languages_sorted = []
    if language_total:
        languages_sorted = sorted(
            (
                (language, round(size / language_total * 100, 2))
                for language, size in language_sizes.items()
            ),
            key=lambda item: item[1],
            reverse=True,
        )

    return SimpleNamespace(
        account_name=user["name"] or username,
        total_followers=followers,
        total_stargazers=stars,
        total_commits_last_year=commits,
        total_pull_requests_made=prs,
        total_issues=issues,
        total_repo_contributions=user["repositoriesContributedTo"]["totalCount"],
        languages_sorted=languages_sorted,
        user_rank=calc_github_rank(
            False, commits, prs, issues, reviews, stars, followers
        ),
    )
