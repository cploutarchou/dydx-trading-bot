# Open Graph Images

This folder contains social media preview images for ExecutionLab pages when shared on social platforms (Twitter, LinkedIn, Discord, Telegram, Facebook, etc.).

## Image Specifications

**Dimensions**: 1200px × 630px (16:9 aspect ratio - optimal for Twitter, Facebook, LinkedIn)
**Format**: PNG or JPG (PNG recommended for transparency support)
**File Size**: Target < 200KB per image
**Color Profile**: RGB (sRGB for web)

## Required Images

### Static Images (Required)

1. **default.png** (1200×630)
   - Fallback image for any page without a specific OG image
   - Should feature ExecutionLab branding and tagline
   - Use case: Articles, unlisted pages, API docs

2. **landing.png** (1200×630)
   - Home page social preview
   - Highlight: Platform value prop, "Build. Test. Execute."
   - Should include ExecutionLab logo and tagline

3. **pricing.png** (1200×630)
   - Pricing page social preview
   - Highlight: Key value tiers, price points
   - Messaging: "Flexible execution partnerships"

4. **ico-launchpad.png** (1200×630)
   - ICO launchpad hub page preview
   - Highlight: "Token Launch" messaging, event/stage information
   - Should include ICO branding elements

5. **ico-document.png** (1200×630)
   - Generic ICO document preview (whitepaper, roadmap, etc.)
   - Fallback for dynamically-loaded document pages
   - Messaging: "Detailed technical documentation"

6. **news.png** (1200×630)
   - News hub page preview
   - Highlight: "Latest Updates" or publication date
   - Use ExecutionLab news/blog icon

7. **service.png** (1200×630)
   - Services/offerings page preview
   - Highlight: Available service tiers
   - Messaging: "Execution partnership solutions"

8. **codex.png** (1200×630)
   - Knowledge base / developer docs preview
   - Highlight: "Reference documentation" or "Developer resources"
   - Use technical documentation visual style

9. **logo.png** (1200×630)
   - Organization branding/logo image
   - Used for schema.org markup
   - Can be simpler/smaller than other OG images

## Design Guidelines

### Color Palette (Dark Fintech Theme)
- **Primary**: Deep slate/navy (#0f172a, #1e293b, #334155)
- **Accent**: Bright cyan/electric blue (#06b6d4, #0ea5e9)
- **Success**: Bright green (#10b981, #34d399)
- **Risk/Warning**: Bright red (#ef4444, #f87171)
- **Text Primary**: White (#ffffff, #f8fafc)
- **Text Secondary**: Light gray (#cbd5e1, #e2e8f0)

### Typography
- **Font Family**: Use system font stack (e.g., -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto)
- **Title Font Size**: 48-72px (bold, white)
- **Body Font Size**: 24-32px (regular, light gray)
- **Line Height**: 1.3-1.4 for readability

### Layout Formula
```
[Left 20% - Logo/Icon] [Center 60% - Main Message] [Right 20% - Branding]

Top margin: 10% from edge
Bottom margin: 10% from edge
Padding: 60-80px around edges
```

### Brand Elements
- **Logo**: ExecutionLab wordmark or symbol (top-left or center-left)
- **Tagline**: "Technical Execution Lab" or "dYdX Trading Platform" (below logo)
- **Call-to-Action**: Optional brief text (bottom-right): "Learn more at executionlab.io"
- **Visual**: Subtle background gradient or pattern (don't overwhelm the text)

## Implementation Status

### ✅ Created (Awaiting Images)
- [x] Folder structure `/public/og-images/`
- [x] Image specification guide (this file)
- [x] Robots.txt with sitemap reference
- [x] Sitemap.xml with OG image references
- [x] SEOHead.tsx component for meta tag injection
- [x] seo.ts utilities for URL building

### ⏳ Needs Completion
- [ ] **default.png** - Generic fallback image
- [ ] **landing.png** - Home page preview
- [ ] **pricing.png** - Pricing page preview
- [ ] **ico-launchpad.png** - ICO hub preview
- [ ] **ico-document.png** - Generic ICO document preview
- [ ] **news.png** - News page preview
- [ ] **service.png** - Services page preview
- [ ] **codex.png** - Documentation page preview
- [ ] **logo.png** - Organization logo image

## Design Tools

**Recommended tools for creating 1200×630 OG images:**

1. **Figma** (free)
   - Template: Search "Open Graph" in community templates
   - Export as PNG at 1x scale to get 1200×630
   - Use design system components for consistency

2. **Canva** (freemium)
   - Template: "Social Media" → "Facebook Cover" (1200×630)
   - Drag-and-drop design with fintech templates
   - Built-in brand kit support

3. **Adobe Express** (freemium)
   - Web-based, easy for quick designs
   - Social media template library
   - Export as PNG

4. **Playwright/Puppeteer** (programmatic)
   - For dynamic OG images (per-page variants)
   - Template HTML → render to PNG at build time
   - Advanced: Integrate with CI/CD pipeline

## Validation & Testing

After creating images, validate using these tools:

### Twitter Card Validator
- URL: https://cards-dev.twitter.com/validator
- Steps:
  1. Paste page URL (e.g., https://executionlab.io/pricing)
  2. Check "Preview" — image should appear with correct dimensions
  3. Verify text doesn't get truncated (title < 70 chars, description < 200 chars)

### Open Graph Debugger (Facebook/Meta)
- URL: https://developers.facebook.com/tools/debug/
- Steps:
  1. Paste page URL
  2. Click "Scrape Again"
  3. Verify og:image URL is fetched (should see thumbnail preview)
  4. Check for warnings/errors in debug output

### Google Rich Results Test
- URL: https://search.google.com/test/rich-results
- Steps:
  1. Paste page URL
  2. Check if JSON-LD schema is recognized
  3. Verify "WebPage" and "Organization" schemas appear

### Manual Testing (Social Platforms)
1. **Twitter**: Post link → check preview before tweeting
2. **LinkedIn**: Share link → wait 60s → check preview
3. **Discord**: Paste link in #announcements → check embed
4. **Telegram**: Message link in chat → check preview

## File Checklist

```bash
# Verify images exist
ls -lh public/og-images/

# Expected output:
# default.png (180K)
# landing.png (190K)
# pricing.png (185K)
# ico-launchpad.png (175K)
# ico-document.png (170K)
# news.png (180K)
# service.png (185K)
# codex.png (175K)
# logo.png (150K)
```

## Maintenance

- **Image updates**: When page content significantly changes, refresh OG image
- **Branding changes**: Update color palette in images if ExecutionLab brand evolves
- **Performance**: Monitor image file sizes — target < 200KB to avoid slow preview loading
- **A/B testing**: Can create variant images (og-images/landing-v2.png) and test CTR/shares

## Next Steps

1. ✅ Create the 9 PNG images (see "Needs Completion" section above)
2. ✅ Run SEOHead component injection into top 3 pages (Landing, Pricing, IcoDocument)
3. ✅ Test on Twitter Card Validator (3+ sample pages)
4. ✅ Test on Open Graph Debugger (3+ sample pages)
5. ✅ Validate JSON-LD on Google Rich Results Test
6. ✅ Share test links on social platforms (Twitter, LinkedIn, Discord) and verify previews
7. ✅ Monitor social media sharing metrics (impressions, engagements)
