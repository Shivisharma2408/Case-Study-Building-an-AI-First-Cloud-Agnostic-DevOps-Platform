import { lazy, Suspense } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import IdeaBoard from "./pages/IdeaBoard";

// The pipelines view is code-split: the Idea Board bundle stays as small as before.
const PipelinesPage = lazy(() => import("./pages/PipelinesPage"));

export default function App() {
  return (
    <>
      <nav className="app-nav" aria-label="Main">
        <span className="app-nav-brand">Idea Board</span>
        <NavLink to="/" end>
          Ideas
        </NavLink>
        <NavLink to="/pipelines">Pipelines</NavLink>
      </nav>
      <Suspense fallback={<p className="app-loading">Loading…</p>}>
        <Routes>
          <Route path="/" element={<IdeaBoard />} />
          <Route path="/pipelines" element={<PipelinesPage />} />
          <Route path="*" element={<IdeaBoard />} />
        </Routes>
      </Suspense>
    </>
  );
}
