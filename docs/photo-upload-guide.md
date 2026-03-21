# Photo upload guide

This project is now organized so photos can be replaced from one predictable location: `public/uploads/`.

## Folder map

| Area | Folder | Notes |
| --- | --- | --- |
| Homepage | `public/uploads/homepage/` | Replace the hero, about, and highlight photos used on the home page. |
| Courses | `public/uploads/courses/` | Replace the photo for each course card using the existing file names. |
| Products | `public/uploads/products/` | Replace the image shown on the product cards. |
| Gallery | `public/uploads/gallery/` | Replace the gallery photos without editing any component code. |

## Easiest way to update photos

1. Open the right folder inside `public/uploads/`.
2. Replace an existing file with a new image using the same file name.
3. Keep the aspect ratio close to the current layout for the best results.
4. Commit and deploy.

If you want to use a completely new file name instead of replacing the existing one, update the related data file:

- Homepage images: `src/data/media-library.ts`
- Courses: `src/data/courses.ts`
- Products: `src/data/products.ts`
- Gallery: `src/data/gallery.ts`

## Recommended image tips

- Use `.webp`, `.jpg`, or `.png` for real photos.
- Keep file names lowercase and use hyphens.
- Aim for clear, bright photos at least 1200px wide.
- Crop course and product photos consistently so cards look neat.
