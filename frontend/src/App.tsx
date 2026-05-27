import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DatasourcePage from "./pages/DatasourcePage";
import DatasetPage from "./pages/DatasetPage";
import QueryPage from "./pages/QueryPage";
import AIQeryPage from "./pages/AIQeryPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Layout />}>
          <Route path="/datasources" element={<DatasourcePage />} />
          <Route path="/datasets" element={<DatasetPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/ai-query" element={<AIQeryPage />} />
          <Route path="/" element={<QueryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
