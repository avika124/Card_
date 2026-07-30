import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Submit from "./pages/Submit";
import MySubmissions from "./pages/MySubmissions";
import ReviewQueue from "./pages/ReviewQueue";
import AllReviews from "./pages/AllReviews";
import ReviewDetail from "./pages/ReviewDetail";
import CompanyMemory from "./pages/CompanyMemory";
import TrainRegulations from "./pages/TrainRegulations";
import RegMonitor from "./pages/RegMonitor";
import Analytics from "./pages/Analytics";
import AuditLog from "./pages/AuditLog";
import Settings from "./pages/Settings";

const REVIEW_ROLES = ["compliance", "legal", "admin"];

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/submit" element={<Submit />} />
            <Route path="/my-submissions" element={<MySubmissions />} />
            <Route path="/submissions/:id" element={<ReviewDetail />} />
            <Route path="/review-queue" element={<ProtectedRoute roles={REVIEW_ROLES}><ReviewQueue /></ProtectedRoute>} />
            <Route path="/all-reviews" element={<ProtectedRoute roles={REVIEW_ROLES}><AllReviews /></ProtectedRoute>} />
            <Route path="/company-memory" element={<CompanyMemory />} />
            <Route path="/train-regulations" element={<TrainRegulations />} />
            <Route path="/reg-monitor" element={<RegMonitor />} />
            <Route path="/analytics" element={<ProtectedRoute roles={REVIEW_ROLES}><Analytics /></ProtectedRoute>} />
            <Route path="/audit-log" element={<ProtectedRoute roles={REVIEW_ROLES}><AuditLog /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute roles={["admin"]}><Settings /></ProtectedRoute>} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
