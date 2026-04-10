import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AgentsProvider } from "./AgentsContext";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AgentsProvider>
      <App />
    </AgentsProvider>
  </StrictMode>
);
