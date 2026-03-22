# Make Up & More School of Cosmetology

A premium, conversion-focused beauty school website built with Next.js App Router, TypeScript, React, and Tailwind CSS. The project is designed for Vercel deployment and uses local static data plus Firestore-backed registration capture so admissions enquiries are saved permanently.

## Features

- Elegant multi-page marketing site for a cosmetology school in Tema.
- Responsive design optimized for mobile, tablet, and desktop.
- SEO-friendly metadata for all core routes.
- Reusable WhatsApp CTA helpers for course, class, and product enquiries.
- Static local data files for courses, upcoming classes, gallery content, testimonials, and products.
- Registration form initializes a Paystack payment and only writes successful registrations to Firestore.
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


## Registration payment + data save (Paystack + Firestore)

Set **server-side** Paystack and Firebase credentials in `.env.local` (and in Vercel project settings) for the `/register` form to process payment and save data:

```bash
# Paystack
NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY=pk_test_xxx
PAYSTACK_SECRET_KEY=sk_test_xxx
# Optional, defaults to 500000 (GHS 5,000.00 if your Paystack account uses pesewas)
REGISTRATION_FEE_KOBO=500000
# Optional, defaults to GHS
PAYSTACK_CURRENCY=GHS

# Option A: individual variables
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CLIENT_EMAIL=your-service-account-client-email
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

# Option B: full JSON as one variable
FIREBASE_SERVICE_ACCOUNT_JSON='{"project_id":"...","client_email":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"}'
```

Notes:
- Registration is written to Firestore **only after** a successful Paystack verification.
- The server validates the verified Paystack transaction status, amount, currency, and customer email before saving a registration.
- `NEXT_PUBLIC_FIREBASE_API_KEY` and other `NEXT_PUBLIC_*` values are for browser SDK use and are **not enough** for secure server writes.
- The server also accepts common aliases (`GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT`, `FIREBASE_ADMIN_CLIENT_EMAIL`, `FIREBASE_ADMIN_PRIVATE_KEY`, `GOOGLE_CLIENT_EMAIL`, `GOOGLE_PRIVATE_KEY`) to simplify Vercel setups.
- Use a Firebase service account with access to Firestore.

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
