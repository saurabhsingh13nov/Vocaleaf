# Wiki Publishing Notes

This folder contains a ready-to-publish GitHub wiki draft for Vocaleaf.

## Included pages

- `Home.md`
- `Product-Tour.md`
- `Technical-Approach.md`
- `Privacy-and-Trust.md`
- `_Sidebar.md`

## Included assets

Images are copied into `wiki/images/` so the wiki can be pushed as a standalone Git repo without depending on the main repository paths.

## Publish to GitHub Wiki

1. Create or enable the repository wiki on GitHub.
2. Clone the wiki repo:

   ```bash
   git clone <your-repo>.wiki.git
   ```

3. Copy the contents of this `wiki/` folder into that cloned wiki repo.
4. Commit and push from the wiki repo.

If you prefer, the same Markdown can also be adapted into repository docs or a marketing microsite later.
