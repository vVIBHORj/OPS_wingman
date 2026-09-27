export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-slate-950 text-slate-100">
      <div className="z-10 max-w-4xl w-full items-center justify-between font-mono text-sm">
        <div className="flex flex-col items-center text-center space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-4 py-1.5 text-xs font-semibold text-sky-400">
            <span className="h-2 w-2 rounded-full bg-sky-400 animate-pulse"></span>
            Phase 0 — Foundation Active
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            OpsWingman
          </h1>

          <p className="max-w-2xl text-base sm:text-lg text-slate-400">
            Intelligent operations platform executing repeatable customer and order workflows across email, orders, payments, logistics, and knowledge — with deterministic policies and permissions outside the LLM.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full pt-8 text-left font-sans">
            <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm">
              <h3 className="font-semibold text-sky-400 text-sm mb-1">Architecture</h3>
              <p className="text-xs text-slate-400">
                Deterministic security perimeter with humans-in-the-loop and strict authorization controls outside the model context.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm">
              <h3 className="font-semibold text-emerald-400 text-sm mb-1">Core Tech Stack</h3>
              <p className="text-xs text-slate-400">
                FastAPI, PostgreSQL + pgvector, Valkey, Mailpit, Next.js, React Flow, and self-hosted Langfuse observability.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm">
              <h3 className="font-semibold text-purple-400 text-sm mb-1">Phase Status</h3>
              <p className="text-xs text-slate-400">
                Phase 0 Foundation established. Services ready for Phase 1 Operational API & Business Simulator.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
