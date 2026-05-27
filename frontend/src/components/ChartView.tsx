import ReactECharts from "echarts-for-react";

interface Props {
  columns: string[];
  rows: any[][];
}

export default function ChartView({ columns, rows }: Props) {
  const numericCols = columns.filter((_, i) => rows.some((r) => typeof r[i] === "number"));

  if (numericCols.length === 0) return <p className="text-gray-400">No numeric columns to chart</p>;

  const option = {
    tooltip: { trigger: "axis" },
    legend: { data: numericCols, textStyle: { color: "#aaa" } },
    xAxis: {
      type: "category",
      data: rows.map((r) => String(r[0])),
      axisLabel: { color: "#888", rotate: 30 },
    },
    yAxis: { type: "value", axisLabel: { color: "#888" } },
    series: numericCols.map((col) => ({
      name: col,
      type: "bar",
      data: rows.map((r) => r[columns.indexOf(col)]),
    })),
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4 mt-4">
      <ReactECharts option={option} style={{ height: 400 }} theme="dark" />
    </div>
  );
}
