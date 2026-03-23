import { readdir } from 'node:fs/promises';
import path from 'node:path';

export type GalleryItem = {
  title: string;
  category: string;
  image: string;
};

const GALLERY_DIR = path.join(process.cwd(), 'public/uploads/gallery');
const GALLERY_WEB_PATH = '/uploads/gallery';

function normalizeTitle(filename: string) {
  return filename
    .replace(/\.[^.]+$/, '')
    .replace(/^WhatsApp Image \d{4}-\d{2}-\d{2} at /, '')
    .replace(/\s*\(\d+\)$/, '')
    .replace(/[._-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function toTitleCase(value: string) {
  return value
    .split(' ')
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

function inferCategory(filename: string) {
  const value = filename.toLowerCase();

  if (value.includes('bridal') || value.includes('makeup') || value.includes('make-up')) {
    return 'Bridal / Makeup Looks';
  }

  if (value.includes('hair') || value.includes('braid')) {
    return 'Hair Work';
  }

  if (value.includes('workshop') || value.includes('workstation') || value.includes('class')) {
    return 'Classroom Training';
  }

  return 'Student Practical Work';
}

export async function getGalleryItems() {
  const entries = await readdir(GALLERY_DIR, { withFileTypes: true });

  return entries
    .filter((entry) => entry.isFile() && /\.(jpe?g|png|webp|avif|svg)$/i.test(entry.name))
    .map((entry) => ({
      title: toTitleCase(normalizeTitle(entry.name)),
      category: inferCategory(entry.name),
      image: `${GALLERY_WEB_PATH}/${entry.name}`
    }))
    .sort((a, b) => a.title.localeCompare(b.title));
}
