import type { MetadataRoute } from 'next';

const routes = ['', '/courses', '/upcoming-classes', '/gallery', '/products', '/register', '/contact'];

export default function sitemap(): MetadataRoute.Sitemap {
  return routes.map((route) => ({
    url: `https://makeup-and-more-school.vercel.app${route}`,
    lastModified: new Date(),
    changeFrequency: route === '' ? 'weekly' : 'monthly',
    priority: route === '' ? 1 : 0.8
  }));
}
