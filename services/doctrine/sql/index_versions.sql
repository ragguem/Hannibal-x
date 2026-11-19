-- Version de l'index (architecture 1.1.0 § 9) : la réindexation y ajoute une ligne, le service lit la dernière
-- et la renvoie dans chaque réponse (gardée dans ops.doctrine_traces). Sans cette table : « passages-<nombre> ».
CREATE TABLE IF NOT EXISTS v2.index_versions (
    version text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    embedding_model text NOT NULL,
    publications text[] NOT NULL,
    passages integer NOT NULL,
    notes text
);
