# Push this repo to your GitHub account

The repository is already initialized with an initial commit on branch `main`. To publish it on GitHub:

## 1. Create a new repository on GitHub

1. Open [https://github.com/new](https://github.com/new).
2. Choose a **Repository name** (e.g. `internet-search-mcp` or `ai-browsing-mcp-stack`).
3. Set visibility to **Public** or **Private**.
4. **Do not** add a README, .gitignore, or license — this repo already has them.
5. Click **Create repository**.

## 2. Add the remote and push

In your terminal, from this project directory, run (replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub username and the repo name you chose):

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

If you use SSH instead of HTTPS:

```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

After the push, the repo will be available at `https://github.com/YOUR_USERNAME/YOUR_REPO`.

## 3. Optional: clone Firecrawl for the full profile

Anyone who clones your repo and wants to run the **full** profile (including Firecrawl) must clone Firecrawl separately, because `firecrawl-src/` is in `.gitignore`:

```bash
git clone https://github.com/mendableai/firecrawl.git firecrawl-src
```

Then they can run `docker compose --profile full up -d`. Your README already documents this.
