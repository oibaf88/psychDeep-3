# psychDeep-vOG repository and deployment rename checklist

## GitHub repository
The connected GitHub actions can create branches, files and pull requests, but do not expose the repository-administration rename operation. A repository administrator must perform this step in GitHub.

1. Open the current repository: https://github.com/oibaf88/psychDeep-3
2. Go to **Settings → General → Repository name**.
3. Change the name to `psychDeep-vOG` and confirm.
4. Verify that https://github.com/oibaf88/psychDeep-vOG resolves and the old URL redirects.
5. Update local clones: `git remote set-url origin https://github.com/oibaf88/psychDeep-vOG.git`.
6. Review GitHub Actions workflows and any third-party integrations that pin the old repository path. GitHub warns that references to Actions hosted in a renamed repository may not redirect.

## Render
Do not rename production services during the GitHub repository rename. Existing service IDs and URLs are externally consumed. After the repository rename:
1. Update the `repo:` value in `render.yaml` to `https://github.com/oibaf88/psychDeep-vOG`.
2. Check each service's repository connection, branch and root directory in Render.
3. Confirm auto-deploy remains on the intended branch and does not deploy this draft PR.
4. Verify the existing environment variables and service IDs have not changed.
5. Perform a controlled staging deploy first; production requires explicit approval.

## Database and clinical continuity
- Do not rename `psychdeep_v12`, database objects, migration IDs, source-table names, or the current Supabase project as part of branding.
- Do not create a replacement database or change `DATABASE_URL`.
- Product label changes must not invalidate patient IDs, consent records, audit trails, source references or model-version history.

## Final verification
- Search repository content for old user-facing names and links.
- Distinguish deliberate compatibility identifiers from obsolete user-facing text.
- Verify GitHub redirects, workflow runs, Render repository connection, frontend title, API health and read-only memory endpoints.
- Record the old/new repository URLs, commit, date, reviewer and any exceptions in the release notes.
