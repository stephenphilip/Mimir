interface Props {
  title: string;
  blurb: string;
}

export function ComingSoon({ title, blurb }: Props) {
  return (
    <section className="panel-page coming-soon" aria-labelledby="soon-title">
      <div className="glass-card soon-card">
        <p className="home-eyebrow">Coming soon</p>
        <h1 id="soon-title">{title}</h1>
        <p>{blurb}</p>
      </div>
    </section>
  );
}
