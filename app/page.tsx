import Link from "next/link";

export default function HomePage() {
  return (
    <div className="landing">
      <h1>Build a demo dataset in minutes</h1>
      <p>
        Answer a short set of questions about your routes and stops, preview the result, and
        download files ready to import into DirectRoute — no file formats to wrangle.
      </p>
      <Link className="primary cta" href="/datasets/new">
        Start the wizard
      </Link>
    </div>
  );
}
