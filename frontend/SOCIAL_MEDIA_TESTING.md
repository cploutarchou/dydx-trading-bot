# Social Media SEO Testing Guide

## 🎯 Quick Test (5 minutes)

Test that **executionlab.io** pages show rich previews when shared on social media.

---

## 🐦 Twitter / X

### Step 1: Get a Page URL
- **Landing**: https://executionlab.io/
- **Pricing**: https://executionlab.io/pricing
- **ICO Document**: https://executionlab.io/ico/executionlab

### Step 2: Validate with Twitter Card Validator
1. Go to https://cards-dev.twitter.com/validator
2. Paste the page URL
3. **Expected Result**: Should show:
   - ✅ Card type: `summary_large_image`
   - ✅ Title: Page-specific (e.g., "Pricing | ExecutionLab")
   - ✅ Description: Page-specific description
   - ✅ Image: Branded 1200×630px preview image

### Step 3: Live Test (Share on Twitter)
1. Log in to Twitter
2. Tweet: "Check out executionlab.io/pricing"
3. **Expected**: Should show card with image, title, description

---

## 📘 Facebook / Threads

### Step 1: Use Open Graph Debugger
1. Go to https://developers.facebook.com/tools/debug/
2. Paste page URL
3. **Expected Result**: Should show:
   - ✅ og:image fetched and displayed
   - ✅ og:title shown
   - ✅ og:description shown
   - ✅ No warnings about missing tags

### Step 2: Live Test (Share on Threads)
1. Go to https://threads.net
2. Paste link
3. **Expected**: Should show card with image and title

---

## 💼 LinkedIn

### Step 1: Share a Link
1. Go to https://www.linkedin.com
2. Click "Share an article"
3. Paste: `https://executionlab.io/pricing`
4. **Expected Result**: Should show:
   - ✅ Branded image
   - ✅ Page title
   - ✅ Page description
   - ✅ Company logo (optional)

### Step 2: Customization
- Click image to choose different preview image (if multiple exist)
- Edit title if it's too long (60 chars recommended)
- Edit description if it's unclear (160 chars recommended)

---

## 💬 Discord

### Step 1: Test in Discord Server
1. Open any Discord channel you have access to
2. Paste: `https://executionlab.io/`
3. **Expected Result**: Should show:
   - ✅ Site name: "ExecutionLab"
   - ✅ Title: Page-specific
   - ✅ Description: Page-specific
   - ✅ Image preview (1200×630px)

### Step 2: Check Embed Details
- Hover over the preview to see full meta information
- Verify og:image URL is absolute (starts with `https://`)

---

## 🔗 Telegram

### Step 1: Share Link
1. Open any Telegram chat
2. Paste: `https://executionlab.io/pricing`
3. **Expected Result**: Should show:
   - ✅ Preview image
   - ✅ Title
   - ✅ Favicon
   - ✅ Domain name

---

## 🔍 Google Search (Rich Snippets)

### Step 1: Rich Results Test
1. Go to https://search.google.com/test/rich-results
2. Paste: `https://executionlab.io/`
3. **Expected Result**: Should show:
   - ✅ Valid structured data (JSON-LD)
   - ✅ Organization schema recognized
   - ✅ WebPage schema recognized
   - ✅ No errors or warnings

### Step 2: Live Search
1. Go to Google
2. Search: `site:executionlab.io`
3. **Expected**: Pages should appear in search results

---

## 🔧 Developer Tools (Browser)

### Check Meta Tags in Browser Console

```javascript
// Copy-paste in browser console on any executionlab.io page:

// Get all meta tags
Array.from(document.querySelectorAll('meta'))
  .map(m => ({ property: m.getAttribute('property') || m.getAttribute('name'), content: m.getAttribute('content') }))
  .filter(m => m.property && m.property.includes('og:') || m.property.includes('twitter:'))

// Output should include:
// { property: "og:title", content: "..." }
// { property: "og:description", content: "..." }
// { property: "og:image", content: "https://..." }
// { property: "twitter:card", content: "summary_large_image" }
```

---

## ✅ Testing Checklist

Use this checklist to verify all pages are working:

### Landing Page (`/`)
- [ ] Twitter Card Validator shows image
- [ ] Open Graph Debugger shows image
- [ ] Discord embed shows preview
- [ ] Title: "ExecutionLab - Advanced Trading Bot Platform"
- [ ] Description: Mentions trading automation
- [ ] Image: `/og-images/landing.png` (exists, <200KB)

### Pricing Page (`/pricing`)
- [ ] Twitter Card Validator shows image
- [ ] Open Graph Debugger shows image
- [ ] Discord embed shows preview
- [ ] Title: "Pricing | ExecutionLab"
- [ ] Description: Mentions flexible partnerships
- [ ] Image: `/og-images/pricing.png`

### ICO Document (`/ico/:slug`)
- [ ] Dynamic title shows ICO name
- [ ] Dynamic description shows ICO details
- [ ] Image: `/og-images/ico-document.png`
- [ ] Twitter validator works for dynamic URL

### Other Pages
- [ ] **IcoLaunchpad**: Image + title + description
- [ ] **News**: Image + title + description
- [ ] **Services**: Image + title + description
- [ ] **Codex**: Image + title + description

---

## 🐛 Troubleshooting

### Issue: Open Graph Debugger shows "Image not found"

**Solution**:
1. Check og:image URL is absolute (starts with `https://`)
2. Verify image file exists: `curl https://executionlab.io/og-images/landing.png`
3. Check image size is 1200×630px
4. Ensure image is PNG or JPG (not WebP)
5. Check file size is <200KB

### Issue: Twitter Card Validator shows "No Card Found"

**Solution**:
1. Verify `twitter:card` meta tag exists
2. Check `twitter:image` is absolute URL
3. Ensure image dimensions are at least 506×506px
4. Wait 24 hours (Twitter caches cards)
5. Click "Preview card" → "Refresh card cache"

### Issue: Discord shows only domain, no preview

**Solution**:
1. Check all og: tags are present
2. Verify og:image URL is publicly accessible
3. Ensure no redirects (og:url should be final URL)
4. Check og:type is `website` or `article`

### Issue: Page title/description is wrong

**Solution**:
1. Verify SEOHead component is imported
2. Check title/description props are passed correctly
3. Verify data is not undefined/null
4. Check for typos in og:title vs og:description
5. Verify text is under length limits (60 chars title, 160 chars description)

---

## 📊 Monitoring

### Daily (After Images Created)
- [ ] Check 1-2 pages on Twitter/Open Graph Debugger
- [ ] Share 1 page on Discord/LinkedIn
- [ ] Verify image appears correctly

### Weekly (After All Pages Complete)
- [ ] Run all pages through Rich Results Test
- [ ] Test each page on all 3 platforms (Twitter, Facebook, Discord)
- [ ] Monitor social analytics for increased link shares

### Monthly (Post-Launch)
- [ ] Track social media referral traffic
- [ ] Monitor click-through rate improvement
- [ ] Update OG images if engagement dips
- [ ] A/B test different image designs

---

## 📞 Support

### For Questions About:
- **Meta tags**: See `src/components/SEOHead.tsx`
- **Image specs**: See `public/og-images/README.md`
- **Implementation**: See `SEO_QUICK_START.md`
- **Full architecture**: See `SEO_IMPLEMENTATION.md`

### Live Domain
**Production**: https://executionlab.io/  
**Development**: http://localhost:5173/ (for local testing)

---

## 🎉 Success Criteria

You'll know it's working when:

✅ All pages show branded image previews on Twitter  
✅ Facebook/Threads shows OG tags without warnings  
✅ Discord shows full embed with image and description  
✅ LinkedIn shows customizable preview card  
✅ Google Search shows JSON-LD schema  
✅ Click-through rate from social increases 30-50%  

**Status**: Ready to test! 🚀
