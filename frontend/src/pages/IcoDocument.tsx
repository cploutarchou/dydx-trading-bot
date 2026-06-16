import { ArrowLeft, ArrowRight, FileText, ShieldAlert } from 'lucide-react';
import { Navigate, useParams } from 'react-router-dom';
import { getCryptoBackgroundVariantForIcoDocument } from '../components/CryptoBackground';
import {
	PublicLaunchShell,
	PublicStatusPill,
	SaleFacts,
	SecondaryButton,
} from '../components/PublicPagePrimitives';
import SEOHead from '../components/SEOHead';
import { getIcoDocument } from '../content/icoDocuments';

export const IcoDocumentPage = () => {
  const { documentSlug } = useParams();
  const document = getIcoDocument(documentSlug);

  if (!document) {
    return <Navigate to="/ico" replace />;
  }

  return (
    <>
      <SEOHead
        title={`${document.title} | ICO | ExecutionLab`}
        description={document.summary}
        image="/og-images/ico-document.png"
        imageAlt={`${document.title} - ICO Documentation`}
        url={`/ico/${document.slug}`}
      />
      <PublicLaunchShell
        logoSubtitle={document.eyebrow}
        backgroundVariant={getCryptoBackgroundVariantForIcoDocument(document.slug)}
        utilityAction={{ label: 'Sign in', to: '/login' }}
      >
        <section className="ico-document-hero">
          <div className="ico-document-hero__copy">
            <PublicStatusPill tone="info" icon={FileText}>
              {document.status}
            </PublicStatusPill>
            <h1>{document.title}</h1>
            <p>{document.summary}</p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <SecondaryButton to="/ico" className="min-h-12 px-5">
                <ArrowLeft className="h-4 w-4" />
                {document.backLabel}
              </SecondaryButton>
              <SecondaryButton to={document.alternatePath} className="min-h-12 px-5">
                {document.alternateLabel}
                <ArrowRight className="h-4 w-4" />
              </SecondaryButton>
            </div>
          </div>
          <aside className="ico-document-summary" aria-label="Document summary">
            <p className="public-eyebrow">Document status</p>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{document.status}</dd>
              </div>
              <div>
                <dt>Last updated</dt>
                <dd>{document.updated}</dd>
              </div>
              <div>
                <dt>Review state</dt>
                <dd>{document.reviewState}</dd>
              </div>
              <div>
                <dt>Briefing</dt>
                <dd>Informational draft</dd>
              </div>
            </dl>
          </aside>
        </section>

        <section className="pb-6 md:pb-8">
          <div className="ico-document-highlight-grid">
            {document.highlights.map((highlight) => (
              <article key={highlight.label} className="ico-document-highlight">
                <p>{highlight.label}</p>
                <h2>{highlight.value}</h2>
                {highlight.helper && <span>{highlight.helper}</span>}
              </article>
            ))}
          </div>
        </section>

        <section className="space-y-6 pb-10 md:pb-12">
          <SaleFacts facts={document.facts} />
        </section>

        <section className="ico-document-layout pb-12 md:pb-16">
          <aside className="ico-document-index" aria-label="Document sections">
            <p className="public-eyebrow">Contents</p>
            <nav>
              {document.sections.map((section) => (
                <a
                  key={section.title}
                  href={`#${section.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                >
                  {section.title}
                </a>
              ))}
            </nav>
          </aside>

          <article className="ico-document-article">
            {document.sections.map((section) => {
              const sectionId = section.title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
              return (
                <section key={section.title} id={sectionId} className="scroll-mt-24">
                  {section.eyebrow && <p className="public-eyebrow">{section.eyebrow}</p>}
                  <h2>{section.title}</h2>
                  {section.body?.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                  {section.callout && (
                    <div className="ico-document-callout" role="note">
                      <ShieldAlert className="h-5 w-5" aria-hidden="true" />
                      <p>{section.callout}</p>
                    </div>
                  )}
                  {section.bullets && (
                    <ul>
                      {section.bullets.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                  {section.table && (
                    <div className="ico-document-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Item</th>
                            <th>Value</th>
                            {section.table.some((row) => row[2]) && <th>Status</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {section.table.map((row) => (
                            <tr key={`${row[0]}-${row[1]}`}>
                              <td>{row[0]}</td>
                              <td>{row[1]}</td>
                              {section.table?.some((tableRow) => tableRow[2]) && (
                                <td>{row[2] ?? ''}</td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              );
            })}
          </article>
        </section>
      </PublicLaunchShell>
    </>
  );
};

export default IcoDocumentPage;
