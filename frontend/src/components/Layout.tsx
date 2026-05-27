import { Link, Outlet, useNavigate } from "react-router-dom";

export default function Layout() {
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <aside className="w-56 bg-gray-900 border-r border-gray-800 p-4 flex flex-col">
        <h1 className="text-lg font-bold text-blue-400 mb-6">ABD Platform</h1>
        <nav className="flex flex-col gap-2 flex-1">
          <Link to="/datasources" className="px-3 py-2 rounded hover:bg-gray-800">Data Sources</Link>
          <Link to="/datasets" className="px-3 py-2 rounded hover:bg-gray-800">Datasets</Link>
          <Link to="/query" className="px-3 py-2 rounded hover:bg-gray-800">Query</Link>
        </nav>
        {token && (
          <button onClick={handleLogout} className="px-3 py-2 text-sm text-gray-400 hover:text-white">
            Logout
          </button>
        )}
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
