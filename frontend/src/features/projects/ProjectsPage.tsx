import { useState } from "react";
import { Link } from "react-router-dom";

import { Ms, Pill } from "../../components/stitch";
import { useResolve } from "../../lib/queries";
import { useTrack } from "../../context/TrackContext";
import { SKILL_NAME } from "../../lib/library";

interface Project {
  id: string;
  title: string;
  level: "Beginner" | "Intermediate" | "Advanced";
  hours: number;
  skills: string[]; // skill (domain) ids
  data: { label: string; url: string };
  why: string;
  steps: string[];
  show: string;
}

/** Portfolio projects on real, public datasets (every link checked on 2026-10-13). */
export const PROJECTS: Project[] = [
  {
    id: "excel-sales",
    title: "Sales dashboard in Excel",
    level: "Beginner",
    hours: 6,
    skills: ["spreadsheets"],
    data: { label: "Alex The Analyst · Excel tutorial files", url: "https://github.com/AlexTheAnalyst/Excel-Tutorial" },
    why: "Almost every analyst job uses Excel. A clean one-page dashboard shows you can tidy data and summarise it.",
    steps: ["Clean the raw sheet: remove duplicates, fix text and dates.", "Build pivot tables: sales by month, region and product.", "Add charts and slicers to one dashboard sheet.", "Write three takeaways in plain words next to the charts."],
    show: "Screenshot the dashboard and share the workbook on GitHub or Google Drive.",
  },
  {
    id: "sql-music",
    title: "Music store questions with SQL",
    level: "Beginner",
    hours: 6,
    skills: ["sql"],
    data: { label: "Chinook sample database", url: "https://github.com/lerocha/chinook-database" },
    why: "Joins, grouping and ranking on a realistic shop database: the exact skills SQL interviews test.",
    steps: ["Load the database (SQLite version is easiest).", "Answer: top 10 customers by spend, best-selling genre per country, monthly revenue.", "Use a window function to rank artists within each genre.", "Write each question and its query in a README."],
    show: "A GitHub repo with your .sql files and a README of questions and answers.",
  },
  {
    id: "sql-cleaning",
    title: "Clean a messy dataset with SQL",
    level: "Intermediate",
    hours: 5,
    skills: ["sql"],
    data: { label: "Alex The Analyst · MySQL series data", url: "https://github.com/AlexTheAnalyst/MySQL-YouTube-Series" },
    why: "Real data is messy. Cleaning it step by step in SQL is a favourite portfolio piece.",
    steps: ["Copy the raw table to a staging table first.", "Remove duplicates with ROW_NUMBER().", "Standardise text, fix dates, handle NULLs and blanks.", "Explore the cleaned data with a few summary queries."],
    show: "Before/after row counts and the cleaning script on GitHub.",
  },
  {
    id: "pandas-netflix",
    title: "Explore Netflix titles with pandas",
    level: "Beginner",
    hours: 6,
    skills: ["python", "python_data", "dataviz"],
    data: { label: "Kaggle · Netflix Movies and TV Shows", url: "https://www.kaggle.com/datasets/shivamb/netflix-shows" },
    why: "A friendly first notebook: loading, cleaning, grouping and charting a dataset everyone understands.",
    steps: ["Load the CSV and check missing values.", "Split the 'listed_in' genres and the date added.", "Group by year and type; find the top countries and genres.", "Make 4–5 clear charts with titles that say the finding."],
    show: "A Kaggle or Jupyter notebook with a short summary at the top.",
  },
  {
    id: "pandas-taxi",
    title: "NYC taxi trips: when and where",
    level: "Intermediate",
    hours: 10,
    skills: ["python_data", "dataviz", "stats"],
    data: { label: "NYC TLC trip record data", url: "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page" },
    why: "Millions of real rows: you learn to work with dates, outliers and big files.",
    steps: ["Download one month of Yellow Taxi trips (Parquet).", "Drop impossible trips (negative fares, zero distance).", "Busiest hours and days; average tip by payment type.", "Map pickups by zone with the zone lookup table."],
    show: "A notebook plus 3 charts you would put in a presentation.",
  },
  {
    id: "stats-ab",
    title: "Run an A/B test analysis",
    level: "Intermediate",
    hours: 5,
    skills: ["stats", "python_data"],
    data: { label: "Kaggle · A/B testing dataset", url: "https://www.kaggle.com/datasets/zhangluyuan/ab-testing" },
    why: "Companies decide product changes with A/B tests. Showing you can read one correctly stands out.",
    steps: ["Check the groups are balanced and remove users seen in both.", "Compare conversion rates; compute the difference and a 95% confidence interval.", "Run a two-proportion z-test and explain the p-value in plain words.", "Recommend: launch, don't launch, or test longer, and why."],
    show: "A one-page write-up with the numbers and your recommendation.",
  },
  {
    id: "viz-gapminder",
    title: "Tell a story with world data",
    level: "Beginner",
    hours: 4,
    skills: ["dataviz"],
    data: { label: "Gapminder data", url: "https://www.gapminder.org/data/" },
    why: "Good charts change minds. Practise picking the right chart and writing a title that makes the point.",
    steps: ["Pick one question (e.g. income vs life expectancy over time).", "Choose the chart type that answers it best.", "Remove clutter, label directly, highlight one thing.", "Write the headline as the takeaway, not the topic."],
    show: "Before/after versions of the chart in a short post.",
  },
  {
    id: "pbi-adventureworks",
    title: "Sales report in Power BI",
    level: "Intermediate",
    hours: 8,
    skills: ["powerbi"],
    data: { label: "Microsoft · Power BI sample datasets", url: "https://learn.microsoft.com/en-us/power-bi/create-reports/sample-datasets" },
    why: "Power BI is the most asked-for BI tool. A star-schema model with good DAX measures is what hiring managers look for.",
    steps: ["Load the sample and build a star schema (facts + dimensions).", "Write measures: total sales, sales last year, year-over-year %.", "Build a 2-page report with slicers and drill-through.", "Publish to the web (or export a PDF) and write what it shows."],
    show: "Screenshots and the .pbix file on GitHub.",
  },
  {
    id: "tableau-superstore",
    title: "Superstore dashboard in Tableau",
    level: "Beginner",
    hours: 5,
    skills: ["tableau"],
    data: { label: "Kaggle · Superstore dataset", url: "https://www.kaggle.com/datasets/vivek468/superstore-dataset-final" },
    why: "The classic Tableau starter. Publishing it on Tableau Public gives you a link to put on your CV.",
    steps: ["Connect to the data and check dimensions vs measures.", "Sales and profit by region, category and month.", "Add a LOD calculation (e.g. each customer's first order).", "Combine 3–4 sheets into one interactive dashboard."],
    show: "Publish on Tableau Public and share the link.",
  },
  {
    id: "dbt-jaffle",
    title: "Build models with dbt",
    level: "Intermediate",
    hours: 6,
    skills: ["data_eng", "sql"],
    data: { label: "dbt Labs · jaffle-shop", url: "https://github.com/dbt-labs/jaffle-shop" },
    why: "dbt is how modern teams turn raw tables into clean, tested ones. This is the official practice project.",
    steps: ["Set up the project and load the seed data.", "Write staging models, then a customers and orders mart.", "Add tests: unique, not_null, relationships.", "Generate the docs site and look at the lineage graph."],
    show: "Your repo plus a screenshot of the lineage graph.",
  },
  {
    id: "de-zoomcamp",
    title: "End-to-end data pipeline",
    level: "Advanced",
    hours: 30,
    skills: ["data_eng", "python", "sql"],
    data: { label: "DataTalksClub · Zoomcamp project guide", url: "https://github.com/DataTalksClub/data-engineering-zoomcamp/tree/main/projects" },
    why: "One project that shows the whole job: ingest, orchestrate, transform, test and serve.",
    steps: ["Pick a public dataset that updates (e.g. taxi trips).", "Ingest it on a schedule with an orchestrator.", "Store it in a warehouse, partitioned by date.", "Transform with dbt and build a small dashboard on top."],
    show: "A repo with an architecture diagram and a 'how to run it' section.",
  },
  {
    id: "ecommerce-capstone",
    title: "E-commerce analysis (capstone)",
    level: "Advanced",
    hours: 20,
    skills: ["sql", "python_data", "stats", "dataviz", "powerbi", "tableau"],
    data: { label: "Kaggle · Brazilian e-commerce (Olist)", url: "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce" },
    why: "Nine linked tables of real orders: a full analyst project from questions to dashboard.",
    steps: ["Write 5 business questions (delivery delays, repeat buyers, top categories…).", "Answer them with SQL joins across the tables.", "Test one idea statistically (e.g. do late deliveries get worse reviews?).", "Present it as a dashboard with a short story."],
    show: "Repo + dashboard link + a 5-slide summary.",
  },
  {
    id: "git-portfolio",
    title: "Put your portfolio online with GitHub Pages",
    level: "Beginner",
    hours: 3,
    skills: ["git"],
    data: { label: "GitHub Pages", url: "https://pages.github.com/" },
    why: "Recruiters look for a link. A simple site listing your projects makes all of them easy to find.",
    steps: ["Create a repo named <your-username>.github.io.", "Add a README or simple HTML page listing your projects.", "Commit and push, using a branch and pull request for each change.", "Link it from your CV and LinkedIn."],
    show: "Your live portfolio URL.",
  },
];

export function ProjectsPage() {
  const { track } = useTrack();
  const r = useResolve(track.goal);
  const [all, setAll] = useState(false);
  const ds = new Set<string>(
    r.data ? (r.data.source === "seed" ? [r.data.domain] : r.data.concepts.map((c) => c.id.split(".")[0] ?? "")) : [],
  );
  const mine = PROJECTS.filter((p) => p.skills.some((s) => ds.has(s)));
  const list = all || !mine.length ? PROJECTS : mine;
  const order = { Beginner: 0, Intermediate: 1, Advanced: 2 };

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-wrap items-end justify-between gap-space-sm">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-md text-headline-md">Projects</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
            Real projects on real public data. Build two or three of these and you have a portfolio to show employers.
            They're ordered from beginner to advanced.
          </p>
        </div>
        {mine.length > 0 && (
          <button type="button" onClick={() => setAll((a) => !a)} className="px-space-md py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-body-sm text-body-sm">
            {all ? "Show projects for my goal" : `Show all ${PROJECTS.length} projects`}
          </button>
        )}
      </header>
      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-space-md">
        {[...list].sort((a, b) => order[a.level] - order[b.level]).map((p) => (
          <article key={p.id} className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
            <div className="flex flex-wrap items-center gap-space-xs">
              <Pill tone={p.level === "Beginner" ? "tertiary" : p.level === "Intermediate" ? "warn" : "error"}>{p.level}</Pill>
              <Pill tone="neutral" icon="schedule">about {p.hours} h</Pill>
              {p.skills.map((s) => (
                <Pill key={s} tone="primary">{SKILL_NAME[s] ?? s}</Pill>
              ))}
            </div>
            <h2 className="font-headline-sm text-headline-sm">{p.title}</h2>
            <p className="font-body-sm text-body-sm text-on-surface-variant">{p.why}</p>
            <ol className="list-decimal pl-5 font-body-sm text-body-sm flex flex-col gap-1">
              {p.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            <p className="font-body-sm text-body-sm"><b>Show it off:</b> {p.show}</p>
            <div className="mt-auto flex flex-wrap gap-space-xs">
              <a href={p.data.url} target="_blank" rel="noreferrer" className="w-fit px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5">
                <Ms name="dataset" size={16} /> Get the data: {p.data.label}
              </a>
              <Link to={`/portfolio?project=${p.id}`} className="w-fit px-space-md py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-body-strong text-body-sm flex items-center gap-1.5">
                <Ms name="badge" size={16} /> I built it: add to portfolio
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
