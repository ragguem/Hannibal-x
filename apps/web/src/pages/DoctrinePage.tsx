import { DoctrinePanel } from "../features/doctrine/DoctrinePanel";
import { GlossarySearch } from "../features/doctrine/GlossarySearch";
import { usePermission } from "../features/session/use-session";

export function DoctrinePage() {
  const canReadGlossary = usePermission("glossary:read");
  return (
    <main className="page doctrine-page">
      <DoctrinePanel title="Assistant de doctrine" />
      {canReadGlossary && <GlossarySearch />}
    </main>
  );
}
