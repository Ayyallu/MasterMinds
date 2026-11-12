"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { CrudSection, type CrudRow } from "@/components/CrudSection";
import { Badge, Card, PageHeader, Tabs, useAsync } from "@/components/ui";

type Tab = "years" | "structure" | "groups";

export default function AcademicPage() {
  const me = useMe();
  const institutionId = me.institution_ids[0];
  const [tab, setTab] = useState<Tab>("years");

  if (!institutionId) {
    return (
      <>
        <PageHeader title="Academic structure" />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Academic structure"
        subtitle="Define the academic framework: years, terms, grades, departments, courses and class groups. Each list supports edit and delete."
      />
      <Tabs
        tabs={[
          { id: "years", label: "Years & terms" },
          { id: "structure", label: "Grades, departments & courses" },
          { id: "groups", label: "Class groups" },
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === "years" && <YearsTab institutionId={institutionId} />}
      {tab === "structure" && <StructureTab institutionId={institutionId} />}
      {tab === "groups" && <GroupsTab institutionId={institutionId} />}
    </>
  );
}

/** Fetch a list to use as <select> options in another form. */
function useOptions(institutionId: number, path: string, label: (r: CrudRow) => string = (r) => String(r.name)) {
  const state = useAsync<CrudRow[]>(() => api(`/institutions/${institutionId}${path}`), [institutionId, path]);
  return {
    options: (state.data ?? []).map((r) => ({ value: r.id, label: label(r) })),
    reload: state.reload,
  };
}

const none = <span className="faint">—</span>;

function YearsTab({ institutionId }: { institutionId: number }) {
  const base = `/institutions/${institutionId}`;
  const years = useOptions(institutionId, "/academic-years");
  const yearName = (id: unknown) => years.options.find((o) => o.value === id)?.label ?? "—";

  return (
    <div className="stack gap-4">
      <div className="grid crud-grid">
        <CrudSection
          title="Academic year"
          noun="academic year"
          basePath={`${base}/academic-years`}
          emptyIcon={<Icon.Calendar size={24} />}
          emptyHint="Create your first academic year to begin."
          fields={[
            { key: "name", label: "Name", required: true, placeholder: "e.g. 2025–2026" },
            { key: "is_current", label: "Mark as current year", type: "checkbox" },
          ]}
          columns={[
            { label: "Name", render: (r) => String(r.name) },
            { label: "Current", render: (r) => (r.is_current ? <Badge tone="success" dot>Current</Badge> : none) },
          ]}
          onChanged={years.reload}
        />
      </div>
      <div className="grid crud-grid">
        <CrudSection
          title="Term"
          noun="term"
          basePath={`${base}/terms`}
          emptyIcon={<Icon.Clock size={24} />}
          emptyHint="Add terms or semesters within an academic year."
          fields={[
            { key: "academic_year_id", label: "Academic year", type: "select", required: true, options: years.options },
            { key: "name", label: "Term name", required: true, placeholder: "e.g. Semester 1" },
            { key: "sequence", label: "Sequence", type: "number", default: 1 },
          ]}
          columns={[
            { label: "Name", render: (r) => String(r.name) },
            { label: "Academic year", render: (r) => yearName(r.academic_year_id) },
            { label: "Sequence", render: (r) => String(r.sequence) },
          ]}
        />
      </div>
    </div>
  );
}

function StructureTab({ institutionId }: { institutionId: number }) {
  const base = `/institutions/${institutionId}`;
  const depts = useOptions(institutionId, "/departments");
  const deptName = (id: unknown) => depts.options.find((o) => o.value === id)?.label ?? "—";

  return (
    <div className="stack gap-4">
      <div className="grid crud-grid">
        <CrudSection
          title="Grade level"
          noun="grade level"
          basePath={`${base}/grade-levels`}
          emptyIcon={<Icon.GraduationCap size={24} />}
          emptyHint="Add grade levels such as Grade 10 or Year 1."
          fields={[{ key: "name", label: "Name", required: true, placeholder: "e.g. Grade 10" }]}
          columns={[{ label: "Name", render: (r) => String(r.name) }]}
        />
      </div>
      <div className="grid crud-grid">
        <CrudSection
          title="Department"
          noun="department"
          basePath={`${base}/departments`}
          emptyIcon={<Icon.Building size={24} />}
          emptyHint="Add departments to group your courses."
          fields={[
            { key: "name", label: "Name", required: true, placeholder: "e.g. Science" },
            { key: "code", label: "Code (optional)", placeholder: "e.g. SCI" },
          ]}
          columns={[
            { label: "Name", render: (r) => String(r.name) },
            { label: "Code", render: (r) => (r.code ? String(r.code) : none) },
          ]}
          onChanged={depts.reload}
        />
      </div>
      <div className="grid crud-grid">
        <CrudSection
          title="Course"
          noun="course"
          basePath={`${base}/courses`}
          emptyIcon={<Icon.Book size={24} />}
          emptyHint="Add the courses or subjects you teach."
          fields={[
            { key: "name", label: "Name", required: true, placeholder: "e.g. Physics" },
            { key: "code", label: "Code", required: true, placeholder: "e.g. PHY101" },
            { key: "department_id", label: "Department (optional)", type: "select", options: depts.options },
          ]}
          columns={[
            { label: "Name", render: (r) => String(r.name) },
            { label: "Code", render: (r) => String(r.code) },
            { label: "Department", render: (r) => (r.department_id ? deptName(r.department_id) : none) },
          ]}
        />
      </div>
    </div>
  );
}

function GroupsTab({ institutionId }: { institutionId: number }) {
  const base = `/institutions/${institutionId}`;
  const grades = useOptions(institutionId, "/grade-levels");
  const terms = useOptions(institutionId, "/terms");
  const courses = useOptions(institutionId, "/courses");
  const label = (opts: { value: number | string; label: string }[], id: unknown) =>
    id ? opts.find((o) => o.value === id)?.label ?? "—" : none;

  return (
    <div className="grid crud-grid">
      <CrudSection
        title="Class group"
        noun="class group"
        basePath={`${base}/class-groups`}
        emptyIcon={<Icon.Users size={24} />}
        emptyHint="Create classes, sections or batches here."
        fields={[
          { key: "name", label: "Name", required: true, placeholder: "e.g. Grade 10 - Section A" },
          {
            key: "kind",
            label: "Kind",
            type: "select",
            required: true,
            numeric: false,
            default: "class",
            options: [
              { value: "class", label: "Class" },
              { value: "section", label: "Section" },
              { value: "batch", label: "Batch" },
            ],
          },
          { key: "grade_level_id", label: "Grade level (optional)", type: "select", options: grades.options },
          { key: "term_id", label: "Term (optional)", type: "select", options: terms.options },
          { key: "course_id", label: "Course (optional)", type: "select", options: courses.options },
        ]}
        columns={[
          { label: "Name", render: (r) => String(r.name) },
          { label: "Kind", render: (r) => <Badge tone="neutral">{String(r.kind)}</Badge> },
          { label: "Grade", render: (r) => label(grades.options, r.grade_level_id) },
          { label: "Term", render: (r) => label(terms.options, r.term_id) },
          { label: "Course", render: (r) => label(courses.options, r.course_id) },
        ]}
      />
    </div>
  );
}
