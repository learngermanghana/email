# Make Up & More School of Cosmetology

A premium, conversion-focused beauty school website built with Next.js App Router, TypeScript, React, and Tailwind CSS. The project is designed for Vercel deployment and uses local static data plus Firestore-backed registration capture so admissions enquiries are saved permanently.

## Features

- Elegant multi-page marketing site for a cosmetology school in Tema.
- Responsive design optimized for mobile, tablet, and desktop.
- SEO-friendly metadata for all core routes.
- Reusable WhatsApp CTA helpers for course, class, and product enquiries.
- Static local data files for courses, upcoming classes, gallery content, testimonials, and products.
- Registration form writes submissions to a Firestore `registrations` collection via the Firestore REST API.
- Sitemap and robots support for better search indexing readiness.

## Project structure

```text
src/
  app/
  components/
  data/
  lib/
public/
  images/
  uploads/
    homepage/
    courses/
    products/
    gallery/
```

## Local setup

1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
3. Open [http://localhost:3000](http://localhost:3000).


## Registration data (Firestore)

Set these environment variables in `.env.local` (and in Vercel project settings) for the `/register` form to save data with Firebase Admin (server-side):

```bash
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CLIENT_EMAIL=your-service-account-client-email
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

Use a Firebase service account with access to Firestore. Because writes happen on the server, Firestore client rules will no longer block submissions with 403 errors.

## Build for production

```bash
npm run build
```

To run the production server locally after building:

```bash
npm run start
```

## Deploy to Vercel

1. Push the repository to GitHub, GitLab, or Bitbucket.
2. Import the project into Vercel.
3. Keep the default framework preset as **Next.js**.
4. Ensure the install command is `npm install` and the build command is `npm run build`.
5. Deploy.

## Updating content

Update these files to manage the main site content:

- Courses: `src/data/courses.ts`
- Upcoming classes: `src/data/upcoming-classes.ts`
- Products: `src/data/products.ts`
- Gallery items: `src/data/gallery.ts`
- Testimonials: `src/data/testimonials.ts`
- Business details and navigation: `src/data/site.ts`

## Uploading photos

All editable site photos now live in `public/uploads/` so it is easier to replace them without searching through the app.

- Homepage photos: `public/uploads/homepage/`
- Course photos: `public/uploads/courses/`
- Product photos: `public/uploads/products/`
- Gallery photos: `public/uploads/gallery/`

If you keep the same file names, you only need to replace the image file. If you want a new file name, update the matching data file as well. See `docs/photo-upload-guide.md` for the full workflow.

## Future integrations

The current implementation is intentionally static and simple to maintain. You can later add:

- **Paystack** for checkout or registration payments.
- **Firebase** for form storage, product inventory, gallery management, or class scheduling.
- A CMS if non-technical staff should update the site.

## Vercel deployment checklist

- [ ] Run `npm install`
- [ ] Run `npm run build`
- [ ] Confirm the production domain for metadata and sitemap URLs
- [ ] Replace placeholder gallery/product imagery with real branded assets
- [ ] Verify WhatsApp number, phone number, and Facebook link
- [ ] Review copy and testimonials before launch
