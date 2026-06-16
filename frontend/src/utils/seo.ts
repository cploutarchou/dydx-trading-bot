/**
 * SEO utilities for meta tag generation and URL handling
 * Handles Open Graph, Twitter Card, and Schema.org markup
 */

const LIVE_URL = import.meta.env.VITE_LIVE_URL || 'https://executionlab.io';
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8888';

export interface MetaTagsConfig {
  title: string;
  description: string;
  image?: string;
  imageAlt?: string;
  url?: string;
  type?: 'website' | 'article';
  twitterHandle?: string;
}

/**
 * Build absolute URL for OG image
 * Ensures all OG images are absolute URLs starting with https://
 */
export function buildOGImageURL(imagePath: string): string {
  if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
    return imagePath;
  }
  // Remove leading slash if present
  const cleanPath = imagePath.startsWith('/') ? imagePath.slice(1) : imagePath;
  return `${LIVE_URL}/${cleanPath}`;
}

/**
 * Build absolute canonical URL
 */
export function buildCanonicalURL(path: string = ''): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${LIVE_URL}${cleanPath}`;
}

/**
 * Get OG image path for a public page
 * Falls back to default if page-specific image doesn't exist
 */
export function getOGImagePath(pageSlug: string): string {
  return `/og-images/${pageSlug}.png`;
}

/**
 * Generate meta tags object for use in React components
 */
export function generateMetaTags(config: MetaTagsConfig) {
  const {
    title,
    description,
    image = getOGImagePath('default'),
    imageAlt = 'ExecutionLab - Technical execution platform for dYdX trading',
    url = buildCanonicalURL(),
    type = 'website',
    twitterHandle = '@executionlab',
  } = config;

  const absoluteImageURL = buildOGImageURL(image);

  return {
    // Standard meta tags
    title,
    description,
    canonical: buildCanonicalURL(url),

    // Open Graph tags
    'og:title': title,
    'og:description': description,
    'og:image': absoluteImageURL,
    'og:image:alt': imageAlt,
    'og:url': buildCanonicalURL(url),
    'og:type': type,
    'og:site_name': 'ExecutionLab',

    // Twitter Card tags
    'twitter:card': 'summary_large_image',
    'twitter:site': twitterHandle,
    'twitter:title': title,
    'twitter:description': description,
    'twitter:image': absoluteImageURL,
    'twitter:image:alt': imageAlt,

    // Additional social tags
    'article:author': 'ExecutionLab',
  };
}

/**
 * Generate Organization schema.org JSON-LD markup
 */
export function generateOrganizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'ExecutionLab',
    url: LIVE_URL,
    logo: buildOGImageURL('/og-images/logo.png'),
    description: 'Technical execution lab for building, testing, and operating dYdX trading bots',
    sameAs: [
      'https://twitter.com/executionlab',
      'https://github.com/executionlab',
      'https://linkedin.com/company/executionlab',
    ],
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: 'Customer Support',
      email: 'support@executionlab.io',
    },
  };
}

/**
 * Generate WebPage schema.org JSON-LD markup
 */
export function generateWebPageSchema(config: MetaTagsConfig) {
  const absoluteImage = buildOGImageURL(config.image || getOGImagePath('default'));
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: config.title,
    description: config.description,
    url: buildCanonicalURL(config.url),
    image: {
      '@type': 'ImageObject',
      url: absoluteImage,
      alt: config.imageAlt || 'Page preview image',
    },
    publisher: {
      '@type': 'Organization',
      name: 'ExecutionLab',
      logo: {
        '@type': 'ImageObject',
        url: buildOGImageURL('/og-images/logo.png'),
      },
    },
  };
}

/**
 * Generate BreadcrumbList schema.org JSON-LD markup
 */
export function generateBreadcrumbSchema(items: Array<{ name: string; url?: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url ? buildCanonicalURL(item.url) : undefined,
    })),
  };
}

/**
 * Get environment variables for SEO
 */
export function getSEOConfig() {
  return {
    liveURL: LIVE_URL,
    apiBaseURL: API_BASE_URL,
  };
}
