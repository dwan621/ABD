import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DatasourcePage from "./pages/DatasourcePage";
import DatasetPage from "./pages/DatasetPage";
import QueryPage from "./pages/QueryPage";
import AIQeryPage from "./pages/AIQeryPage";
import InsightsPage from "./pages/InsightsPage";
import LineagePage from "./pages/LineagePage";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Layout />}>
          <Route path="/datasources" element={<DatasourcePage />} />
          <Route path="/datasets" element={<DatasetPage />} />
          <Route path="/datasets/:id" element={<DatasetDetailPage />} />
          <Route path="/datasets/:id/lineage" element={<LineagePage />} />
          <Route path="/datasets/:id/insights" element={<InsightsPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/ai-query" element={<AIQeryPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/" element={<QueryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
