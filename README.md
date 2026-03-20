# Make Up & More School of Cosmetology

A premium, conversion-focused beauty school website built with Next.js App Router, TypeScript, React, and Tailwind CSS. The project is designed for Vercel deployment and uses local static data so content can be updated without adding a database yet.

## Features

- Elegant multi-page marketing site for a cosmetology school in Tema.
- Responsive design optimized for mobile, tablet, and desktop.
- SEO-friendly metadata for all core routes.
- Reusable WhatsApp CTA helpers for course, class, product, and registration enquiries.
- Static local data files for courses, upcoming classes, gallery content, testimonials, and products.
- Simple structure that is ready for future Paystack and Firebase integration.
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
