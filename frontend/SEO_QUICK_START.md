# Quick SEOHead Implementation Guide

This guide shows how to add SEOHead to remaining public pages (IcoLaunchpad, News, PublicServicePage, Codex).

## Copy-Paste Template

### Step 1: Add Import
At the top of your page file, add:
```typescript
import SEOHead from '../components/SEOHead';
```

### Step 2: Wrap Return with Fragment
Change:
```typescript
return (
  <YourShell>
    {/* content */}
  </YourShell>
);
```

To:
```typescript
return (
  <>
    <SEOHead
      title="YOUR TITLE HERE"
      description="YOUR DESCRIPTION HERE"
      image="/og-images/your-image.png"
    />
    <YourShell>
      {/* content */}
    </YourShell>
  </>
);
```

### Step 3: Close Fragment
At the end of the return, change:
```typescript
  </YourShell>
);
```

To:
```typescript
  </YourShell>
  </>
);
```

---

## Page-by-Page Templates

### 1. IcoLaunchpad.tsx

**Location**: `src/pages/IcoLaunchpad.tsx`

```typescript
// Add import
import SEOHead from '../components/SEOHead';

// In component return statement:
<SEOHead
  title="ICO Launchpad | ExecutionLab"
  description="Launch and explore token offerings on ExecutionLab. Access verified ICO documentation, whitepapers, and project details."
  image="/og-images/ico-launchpad.png"
  imageAlt="ExecutionLab ICO Launchpad - Token launch platform"
  url="/ico"
/>
```

---

### 2. News.tsx

**Location**: `src/pages/News.tsx`

```typescript
// Add import
import SEOHead from '../components/SEOHead';

// In component return statement:
<SEOHead
  title="News & Updates | ExecutionLab"
  description="Latest news, announcements, and updates from ExecutionLab. Stay informed about platform launches, features, and partnerships."
  image="/og-images/news.png"
  imageAlt="ExecutionLab News and Updates"
  url="/news"
/>
```

---

### 3. PublicServicePage.tsx

**Location**: `src/pages/PublicServicePage.tsx`

```typescript
// Add import
import SEOHead from '../components/SEOHead';

// In component return statement:
<SEOHead
  title="Services | ExecutionLab"
  description="ExecutionLab services: technical execution lab for building, testing, and operating production-grade dYdX trading systems."
  image="/og-images/service.png"
  imageAlt="ExecutionLab Services - Execution partnership solutions"
  url="/service"
/>
```

---

### 4. Codex.tsx

**Location**: `src/pages/Codex.tsx`

```typescript
// Add import
import SEOHead from '../components/SEOHead';

// In component return statement:
<SEOHead
  title="Codex | Developer Documentation | ExecutionLab"
  description="ExecutionLab Codex: comprehensive reference documentation for building and operating dYdX trading bots."
  image="/og-images/codex.png"
  imageAlt="ExecutionLab Codex - Developer reference and documentation"
  url="/codex"
/>
```

---

## Testing After Implementation

After adding SEOHead to a page:

1. **Local Test**:
   ```bash
   npm run dev
   # Navigate to the page in browser
   # Open DevTools → Elements → Head
   # Verify <title>, <meta> tags are present
   ```

2. **Lint Check**:
   ```bash
   npm run lint
   # Should return 0 errors, 0 warnings
   ```

3. **Social Media Test** (after deploying):
   - Twitter: https://cards-dev.twitter.com/validator
   - Facebook: https://developers.facebook.com/tools/debug/
   - Paste page URL, verify og:image appears

---

## Troubleshooting

### Meta tags not appearing?
- Verify SEOHead is mounted BEFORE other content
- Check browser DevTools → Elements → Head → scroll to find `<meta property="og:*">`
- Ensure page is not lazy-loaded (should be in main Routes)

### Image not showing in preview?
- Verify image file exists: `ls -lh public/og-images/your-image.png`
- Verify URL is absolute: should start with `https://`
- Test URL directly in browser: `https://executionlab.io/og-images/your-image.png`
- Wait 24h for social platform cache to clear

### TypeScript error?
- Import must be exactly: `import SEOHead from '../components/SEOHead'`
- Props must match `MetaTagsConfig` interface (title, description required; image optional)

### Title not updating?
- Clear browser cache: Ctrl+Shift+Delete
- Verify SEOHead is in component JSX
- Check document.title in DevTools Console: `document.title`

---

## Full Working Example: IcoLaunchpad.tsx

```typescript
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import SEOHead from '../components/SEOHead'; // ← ADD THIS
import PublicLaunchShell from '../components/PublicLaunchShell';
// ... other imports

export const IcoLaunchpadPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  // ... component logic

  return (
    <> {/* ← ADD FRAGMENT OPENING */}
      <SEOHead {/* ← ADD SEOHEAD COMPONENT */}
        title="ICO Launchpad | ExecutionLab"
        description="Launch and explore token offerings on ExecutionLab. Access verified ICO documentation, whitepapers, and project details."
        image="/og-images/ico-launchpad.png"
        imageAlt="ExecutionLab ICO Launchpad - Token launch platform"
        url="/ico"
      />
      <PublicLaunchShell>
        {/* ... existing page content ... */}
      </PublicLaunchShell>
    </> {/* ← ADD FRAGMENT CLOSING */}
  );
};

export default IcoLaunchpadPage;
```

---

## SEOHead Props Reference

```typescript
interface MetaTagsConfig {
  title: string;           // Page title (required)
  description: string;     // Meta description (required)
  image?: string;          // OG image path (optional, default: /og-images/default.png)
  imageAlt?: string;       // Image alt text (optional)
  url?: string;            // Canonical URL path (optional, auto-detected from route)
  type?: 'website' | 'article'; // OG type (optional, default: 'website')
  twitterHandle?: string;  // Twitter handle (optional, default: '@executionlab')
}
```

---

## Performance Notes

- SEOHead adds < 1KB gzipped to bundle
- Meta tag injection is O(n) where n = number of tags (typically 15-20)
- JSON-LD schemas add 0.5-1.5KB per page
- No impact on First Contentful Paint (FCP) - injected in useEffect

---

## When to Update Page Titles/Descriptions

**Update SEOHead if**:
- Page content changes significantly
- Brand messaging updates
- Key features added/removed
- Target keywords change
- Page URL structure changes

**Timing**: Update immediately for important messaging, revalidate socially every 6 months

---

## Common Patterns

### Dynamic Title (from URL param):
```typescript
const { documentSlug } = useParams();
const document = getIcoDocument(documentSlug);

<SEOHead
  title={`${document.title} | ICO | ExecutionLab`} // ← Dynamic
  description={document.summary}
  image="/og-images/ico-document.png"
  url={`/ico/${document.slug}`}
/>
```

### Conditional Description:
```typescript
<SEOHead
  title="News | ExecutionLab"
  description={isLoading ? "Loading latest news..." : "Latest ExecutionLab news and updates"} 
  image="/og-images/news.png"
/>
```

### Array of Images (for gallery pages):
```typescript
// If you want per-item OG images in future, preload paths:
const imagePath = `/og-images/news/${newsSlug}.png`;

<SEOHead
  title={newsTitle}
  description={newsExcerpt}
  image={imagePath} // ← Will validate and make absolute
/>
```

---

## See Also

- **Full Guide**: [SEO_IMPLEMENTATION.md](./SEO_IMPLEMENTATION.md)
- **Image Specs**: [public/og-images/README.md](./public/og-images/README.md)
- **Utilities**: [src/utils/seo.ts](./src/utils/seo.ts)
- **Component**: [src/components/SEOHead.tsx](./src/components/SEOHead.tsx)

---

**Last Updated**: 2026-06-16  
**Status**: Ready for implementation
