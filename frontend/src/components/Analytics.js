import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import "./Analytics.css";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(
  LineElement,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend
);

const Analytics = () => {
  const [analytics, setAnalytics] = useState({
    total_pdfs: 0,
    top_review_fields: [],
    lowest_accuracy_pdf: null,
    field_confidences: {},
    pdfs: []
  });
  const [trend, setTrend] = useState([]);
  const [filter, setFilter] = useState("all");

  const fetchAnalytics = useCallback(async () => {
    try {
      const user_id = localStorage.getItem("token");

      const res = await axios.post("/analytics", {
        filter,
        user_id,
      });

      const pdfRes = await axios.post("/analytics/pdf-details", {
        user_id,
      });

      const combinedAnalytics = {
        total_pdfs: res.data.total_pdfs || 0,
        top_review_fields: res.data.top_review_fields || [],
        lowest_accuracy_pdf: res.data.lowest_accuracy_pdf || null,
        field_confidences: res.data.field_confidences || {},
        pdfs: pdfRes.data.pdfs || []
      };

      console.log("✅ Combined Analytics:", combinedAnalytics);
      setAnalytics(combinedAnalytics);
    } catch (err) {
      console.error("Analytics Error:", err);
    }
  }, [filter]);

  const fetchTrendData = useCallback(async () => {
    try {
      const user_id = localStorage.getItem("token");
      const res = await axios.post("/analytics/trends", {
        filter,
        user_id,
      });
      setTrend(res.data.trend);
    } catch (err) {
      console.error("Trend Error:", err);
    }
  }, [filter]);

  useEffect(() => {
    fetchAnalytics();
    fetchTrendData();
  }, [fetchAnalytics, fetchTrendData]);

  return (
    <div className="analytics-container">
      <h2>📊 PDF Extraction Analytics</h2>

      <div className="filter-options">
        <label>
          <input
            type="radio"
            value="all"
            checked={filter === "all"}
            onChange={(e) => setFilter(e.target.value)}
          />
          All
        </label>
        <label>
          <input
            type="radio"
            value="day"
            checked={filter === "day"}
            onChange={(e) => setFilter(e.target.value)}
          />
          Today
        </label>
        <label>
          <input
            type="radio"
            value="week"
            checked={filter === "week"}
            onChange={(e) => setFilter(e.target.value)}
          />
          Past 7 Days
        </label>
        <label>
          <input
            type="radio"
            value="month"
            checked={filter === "month"}
            onChange={(e) => setFilter(e.target.value)}
          />
          This Month
        </label>
      </div>

      <div className="top-cards">
        <div className="card">📄 PDFs Processed: {analytics.total_pdfs ?? 0}</div>
        <div className="card">
          ⚠️ Top Review Fields:{" "}
          {analytics.top_review_fields?.length > 0
            ? analytics.top_review_fields
                .map((f) =>
                  f === "issueDate"
                    ? "Issue Date"
                    : f === "contractAmount"
                    ? "Contract Amount"
                    : f.charAt(0).toUpperCase() + f.slice(1)
                )
                .join(", ")
            : "N/A"}
        </div>
        <div className="card">
          ⛔ Lowest Accuracy File:{" "}
          {analytics.lowest_accuracy_pdf?.pdfName || "N/A"} (
          {analytics.lowest_accuracy_pdf?.accuracy?.toFixed(1) ?? "0.0"}%)
        </div>
      </div>

      <div className="charts">
        <div className="chart-box">
          <h3>📈 Accuracy Trend</h3>
          <Bar
            data={{
              labels: trend.map((d) => d.date),
              datasets: [
                {
                  label: "Avg Accuracy (%)",
                  data: trend.map((d) =>
                    d.avg_accuracy != null ? d.avg_accuracy.toFixed(2) : 0
                  ),
                  backgroundColor: "#4e79a7",
                },
              ],
            }}
            options={{
              scales: {
                y: {
                  min: 0,
                  max: 100,
                  ticks: {
                    callback: (value) => value + "%",
                  },
                  title: {
                    display: true,
                    text: "Accuracy (%)",
                  },
                },
              },
            }}
          />
        </div>

        <div className="chart-box">
          <h3>📊 Field-Wise Confidence</h3>
          <Bar
            data={{
              labels: Object.keys(analytics.field_confidences || {}).map((key) =>
                key === "issueDate"
                  ? "Issue Date"
                  : key === "contractAmount"
                  ? "Contract Amount"
                  : key.charAt(0).toUpperCase() + key.slice(1)
              ),
              datasets: [
                {
                  label: "Confidence (%)",
                  data: Object.values(analytics.field_confidences || {}).map((val) =>
                    parseFloat(val)
                  ),
                  backgroundColor: "#f28e2c",
                },
              ],
            }}
            options={{
              scales: {
                y: {
                  min: 0,
                  max: 100,
                  ticks: {
                    callback: (value) => value + "%",
                  },
                },
              },
            }}
          />
        </div>
      </div>

      <div className="pdf-list-section">
        <h3>📂 Extracted PDFs</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>PDF Name</th>
              <th>Accuracy (%)</th>
              <th>Name Conf.</th>
              <th>Amount Conf.</th>
              <th>Issue Date Conf.</th>
              <th>Pages</th>
              <th>Words</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {analytics.pdfs?.map((pdf, index) => (
              <tr key={index}>
                <td>{pdf.pdfName}</td>
               <td>{pdf.accuracy != null ? pdf.accuracy.toFixed(1) : "-"}</td>

                <td>{pdf.field_confidences?.name ?? "-"}</td>
<td>{pdf.field_confidences?.contractAmount ?? "-"}</td>
<td>{pdf.field_confidences?.issueDate ?? "-"}</td>

                <td>{pdf.pageCount ?? "-"}</td>
                <td>{pdf.wordCount ?? "-"}</td>
                <td>{pdf.timestamp || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Analytics;
