"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { InstitutionProfileCard, useInstitutionProfile } from "@/components/Institution";
import {
  AsyncView,
  Button,
  Card,
  PageHeader,
  Stat,
  useAsync,
} from "@/components/ui";
import { primaryRoleLabel, type Me } from "@/lib/session";

type Registration = { id: number; status: string };

export default function AdminOverview() {
  const me = useMe();
  return me.is_super_admin ? <SuperAdminOverview me={me} /> : <InstitutionOverview me={me} />;
}

function QuickLink({ href, icon, title, body }: { href: string; icon: React.ReactNode; title: string; body: string }) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Card interactive className="stack gap-2" style={{ height: "100%" }}>
        <span className="stat-icon" style={{ width: 38, height: 38 }}>
          {icon}
        </span>
        <span className="card-title" style={{ marginTop: "var(--s-2)" }}>
          {title}
        </span>
        <span className="muted text-sm">{body}</span>
      </Card>
    </Link>
  );
}

function SuperAdminOverview({ me }: { me: Me }) {
  const state = useAsync<Registration[]>(
    () => api<Registration[]>("/admin/registrations?status_filter=pending"),
    [],
  );

  return (
    <>
      <PageHeader
        title={`Welcome, ${me.full_name.split(" ")[0]}`}
        subtitle="Platform administration — review institutions, manage the global library and audit activity."
      />
      <div className="grid grid-stats" style={{ marginBottom: "var(--s-8)" }}>
        <Stat
          label="Pending registrations"
          value={state.loading ? "—" : (state.data?.length ?? 0)}
          icon={<Icon.Inbox size={18} />}
          foot={<Link href="/admin/registrations">Review requests →</Link>}
        />
        <Stat label="Role" value={primaryRoleLabel(me)} icon={<Icon.Shield size={18} />} />
      </div>
      <h2 style={{ marginBottom: "var(--s-4)" }}>Jump back in</h2>
      <div className="grid grid-cards">
        <QuickLink href="/admin/registrations" icon={<Icon.Inbox size={20} />} title="Registrations" body="Approve or reject institution registration requests and provision admins." />
        <QuickLink href="/admin/institutions" icon={<Icon.Building size={20} />} title="Institutions" body="Create schools and colleges, edit their profiles and control access." />
        <QuickLink href="/admin/global" icon={<Icon.Globe size={20} />} title="Global library" body="Generate and review shared questions available to all institutions." />
        <QuickLink href="/admin/reports" icon={<Icon.Chart size={20} />} title="Reports" body="Audited cross-tenant exam reporting." />
      </div>
    </>
  );
}

function InstitutionOverview({ me }: { me: Me }) {
  const institutionId = me.institution_ids[0];
  const isAdmin = me.roles.includes("institution_admin");
  const profile = useInstitutionProfile(institutionId);

  const state = useAsync(
    async () => {
      if (!institutionId) return { classGroups: 0, years: 0 };
      const [cg, ay] = await Promise.all([
        api<unknown[]>(`/institutions/${institutionId}/class-groups`).catch(() => []),
        api<unknown[]>(`/institutions/${institutionId}/academic-years`).catch(() => []),
      ]);
      return { classGroups: cg.length, years: ay.length };
    },
    [institutionId],
  );

  return (
    <>
      <PageHeader
        title={`Welcome, ${me.full_name.split(" ")[0]}`}
        subtitle={`${primaryRoleLabel(me)} workspace — author questions, build exams and publish results.`}
      />
      {!institutionId ? (
        <Card>
          <p className="muted">
            No institution is linked to your account yet. Ask your Super Admin to provision your
            institution membership.
          </p>
        </Card>
      ) : (
        <>
          {profile.data && (
            <div style={{ marginBottom: "var(--s-8)" }}>
              <InstitutionProfileCard profile={profile.data} canEditLogo={isAdmin} onChanged={() => void profile.reload()} />
            </div>
          )}
          {isAdmin && (
            <AsyncView state={state}>
              {(d) => (
                <div className="grid grid-stats" style={{ marginBottom: "var(--s-8)" }}>
                  <Stat label="Class groups" value={d.classGroups} icon={<Icon.Users size={18} />} foot={<Link href="/admin/academic">Manage →</Link>} />
                  <Stat label="Academic years" value={d.years} icon={<Icon.Calendar size={18} />} foot={<Link href="/admin/academic">Manage →</Link>} />
                </div>
              )}
            </AsyncView>
          )}
          <h2 style={{ marginBottom: "var(--s-4)" }}>Jump back in</h2>
          <div className="grid grid-cards">
            {isAdmin && (
              <>
                <QuickLink href="/admin/academic" icon={<Icon.Layers size={20} />} title="Academic structure" body="Years, terms, grades, departments, courses and class groups." />
                <QuickLink href="/admin/people" icon={<Icon.Users size={20} />} title="People" body="Invite staff, approve students, enroll and import rosters." />
              </>
            )}
            <QuickLink href="/admin/questions" icon={<Icon.FileText size={20} />} title="Question bank" body="Author versioned questions, search and review." />
            <QuickLink href="/admin/ai" icon={<Icon.Sparkles size={20} />} title="AI generation" body="Generate reviewed question candidates pre-exam." />
            <QuickLink href="/admin/exams" icon={<Icon.ClipboardCheck size={20} />} title="Exams" body="Draft, submit, schedule and manage exam lifecycle." />
            <QuickLink href="/admin/results" icon={<Icon.Chart size={20} />} title="Results & reports" body="Score, publish and export exam reports." />
          </div>
          {!isAdmin && (
            <Card style={{ marginTop: "var(--s-6)" }}>
              <div className="row gap-3 items-start">
                <Icon.Info size={18} />
                <p className="muted text-sm" style={{ margin: 0 }}>
                  As Faculty you can draft and submit exams within your assigned class groups.
                  Approval, scheduling and result publishing are performed by an Institution Admin.
                </p>
              </div>
            </Card>
          )}
        </>
      )}
    </>
  );
}
