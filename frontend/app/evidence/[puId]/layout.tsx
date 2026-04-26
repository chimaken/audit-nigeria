/**
 * PU ids are not known at build time; export a placeholder page and rely on client navigation
 * for real ids. Direct-load of arbitrary `/evidence/<id>` may 404 on static hosting until
 * that HTML exists — prefer in-app links from seeded LGA/state views.
 */
export function generateStaticParams() {
  return [{ puId: "0" }];
}

export default function EvidenceSegmentLayout({ children }: { children: React.ReactNode }) {
  return children;
}
