import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <main className="page narrow">
      <h1>Page introuvable</h1>
      <p>
        <Link className="btn" to="/">
          Retour à la préparation
        </Link>
      </p>
    </main>
  );
}
