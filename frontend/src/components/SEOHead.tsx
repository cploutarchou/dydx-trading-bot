import React, { useEffect } from 'react';
import {
    generateMetaTags,
    generateOrganizationSchema,
    generateWebPageSchema,
    type MetaTagsConfig,
} from '../utils/seo';

interface SEOHeadProps extends MetaTagsConfig {
  /** Additional JSON-LD schemas to inject (e.g., BreadcrumbList, Article, Product) */
  schemas?: Array<Record<string, unknown>>;
  /** Whether to include Organization schema (default: true) */
  includeOrganization?: boolean;
  /** Whether to include WebPage schema (default: true) */
  includeWebPage?: boolean;
}

/**
 * SEOHead Component
 *
 * Manages page-level SEO meta tags, Open Graph, Twitter Card, and JSON-LD schema
 * Inject this component at the top level of any public-facing page
 *
 * Usage:
 * ```tsx
 * <SEOHead
 *   title="Backtesting | ExecutionLab"
 *   description="Backtest your dYdX trading strategies"
 *   image="/og-images/backtesting.png"
 * />
 * ```
 */
export const SEOHead: React.FC<SEOHeadProps> = ({
  title,
  description,
  image,
  imageAlt,
  url,
  type,
  twitterHandle,
  schemas = [],
  includeOrganization = true,
  includeWebPage = true,
}) => {
  useEffect(() => {
    // Generate all meta tags
    const tags = generateMetaTags({
      title,
      description,
      image,
      imageAlt,
      url,
      type,
      twitterHandle,
    });

    // Update document title
    document.title = tags.title;

    // Helper function to add/update meta tag
    const setMetaTag = (name: string, content: string) => {
      const attribute = name.startsWith('og:') || name.startsWith('twitter:') ? 'property' : 'name';
      let element = document.querySelector(
        `meta[${attribute}="${name}"]`
      ) as HTMLMetaElement | null;

      if (!element) {
        element = document.createElement('meta');
        element.setAttribute(attribute, name);
        document.head.appendChild(element);
      }

      element.content = content;
    };

    // Helper function to add/update link tag
    const setLinkTag = (rel: string, href: string) => {
      let element = document.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;

      if (!element) {
        element = document.createElement('link');
        element.rel = rel;
        document.head.appendChild(element);
      }

      element.href = href;
    };

    // Set standard meta tags
    setMetaTag('description', tags.description);
    setMetaTag('og:title', tags['og:title']);
    setMetaTag('og:description', tags['og:description']);
    setMetaTag('og:image', tags['og:image']);
    setMetaTag('og:image:alt', tags['og:image:alt']);
    setMetaTag('og:url', tags['og:url']);
    setMetaTag('og:type', tags['og:type']);
    setMetaTag('og:site_name', tags['og:site_name']);

    // Set Twitter Card tags
    setMetaTag('twitter:card', tags['twitter:card']);
    setMetaTag('twitter:site', tags['twitter:site']);
    setMetaTag('twitter:title', tags['twitter:title']);
    setMetaTag('twitter:description', tags['twitter:description']);
    setMetaTag('twitter:image', tags['twitter:image']);
    setMetaTag('twitter:image:alt', tags['twitter:image:alt']);

    // Set canonical URL
    setLinkTag('canonical', tags.canonical);

    // Clean up and add/update JSON-LD schemas
    let schemaScript = document.querySelector(
      'script[data-seo-head="organization"]'
    ) as HTMLScriptElement | null;
    if (includeOrganization) {
      if (!schemaScript) {
        schemaScript = document.createElement('script');
        schemaScript.type = 'application/ld+json';
        schemaScript.setAttribute('data-seo-head', 'organization');
        document.head.appendChild(schemaScript);
      }
      schemaScript.textContent = JSON.stringify(generateOrganizationSchema());
    } else if (schemaScript) {
      schemaScript.remove();
    }

    // Add WebPage schema
    let webpageScript = document.querySelector(
      'script[data-seo-head="webpage"]'
    ) as HTMLScriptElement | null;
    if (includeWebPage) {
      if (!webpageScript) {
        webpageScript = document.createElement('script');
        webpageScript.type = 'application/ld+json';
        webpageScript.setAttribute('data-seo-head', 'webpage');
        document.head.appendChild(webpageScript);
      }
      webpageScript.textContent = JSON.stringify(
        generateWebPageSchema({
          title,
          description,
          image,
          imageAlt,
          url,
          type,
        })
      );
    } else if (webpageScript) {
      webpageScript.remove();
    }

    // Add additional schemas
    schemas.forEach((schema, index) => {
      let script = document.querySelector(
        `script[data-seo-head="schema-${index}"]`
      ) as HTMLScriptElement | null;
      if (!script) {
        script = document.createElement('script');
        script.type = 'application/ld+json';
        script.setAttribute('data-seo-head', `schema-${index}`);
        document.head.appendChild(script);
      }
      script.textContent = JSON.stringify(schema);
    });

    return () => {
      // Note: We don't clean up meta tags on unmount to preserve them for the next page
      // Only clean up additional schemas
      schemas.forEach((_, index) => {
        const script = document.querySelector(`script[data-seo-head="schema-${index}"]`);
        script?.remove();
      });
    };
  }, [
    title,
    description,
    image,
    imageAlt,
    url,
    type,
    twitterHandle,
    schemas,
    includeOrganization,
    includeWebPage,
  ]);

  return null;
};

