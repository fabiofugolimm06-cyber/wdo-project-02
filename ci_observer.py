import os
import time
import requests

OWNER = "SEU_USER_GITHUB"
REPO = "WDO-PROJECT-02"
TOKEN = os.getenv("GITHUB_TOKEN")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

def get_latest_run():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs"
    r = requests.get(url, headers=headers)
    data = r.json()
    run = data["workflow_runs"][0]

    return {
        "name": run["name"],
        "status": run["status"],
        "conclusion": run["conclusion"],
        "url": run["html_url"],
        "commit": run["head_sha"][:7]
    }

def loop():
    last = None

    while True:
        try:
            run = get_latest_run()

            if run != last:
                print("\n==============================")
                print(f"CI: {run['name']}")
                print(f"Commit: {run['commit']}")
                print(f"Status: {run['status']}")
                print(f"Result: {run['conclusion']}")
                print(f"URL: {run['url']}")
                print("==============================\n")

                last = run

            time.sleep(10)

        except Exception as e:
            print("Erro no observer:", e)
            time.sleep(10)

if __name__ == "__main__":
    loop()