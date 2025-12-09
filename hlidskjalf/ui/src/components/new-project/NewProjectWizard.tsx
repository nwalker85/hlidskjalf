"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Server,
  Database,
  Globe,
  GitBranch,
  Box,
  Layers,
  Code2,
  Network,
  ExternalLink,
} from "lucide-react";

// Types matching backend models
interface Template {
  id: string;
  name: string;
  description: string;
  features: string[];
}

interface Category {
  id: string;
  name: string;
  api_range: string;
  ui_range: string;
}

interface Realm {
  id: string;
  name: string;
  description: string;
}

interface PortAllocation {
  category: string;
  api_port: number;
  ui_port: number;
}

interface ScaffoldRequest {
  name: string;
  description: string;
  category: string;
  realm: string;
  template: string;
  group: string;
  include_api: boolean;
  include_ui: boolean;
  include_worker: boolean;
  use_postgres: boolean;
  use_redis: boolean;
  use_nats: boolean;
  use_livekit: boolean;
  isolated_network: boolean;
}

interface ScaffoldResult {
  id: string;
  name: string;
  gitlab_web_url: string;
  subdomain: string;
}

const STEPS = [
  { id: "basics", label: "Basics" },
  { id: "template", label: "Template" },
  { id: "services", label: "Services" },
  { id: "dependencies", label: "Dependencies" },
  { id: "review", label: "Review" },
];

export function NewProjectWizard({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (project: ScaffoldResult) => void;
}) {
  // Wizard state
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScaffoldResult | null>(null);

  // Reference data
  const [templates, setTemplates] = useState<Template[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [realms, setRealms] = useState<Realm[]>([]);
  const [portPreview, setPortPreview] = useState<PortAllocation | null>(null);

  // Form state
  const [formData, setFormData] = useState<ScaffoldRequest>({
    name: "",
    description: "",
    category: "work",
    realm: "midgard",
    template: "ravenmaskos",
    group: "ravenhelm",
    include_api: true,
    include_ui: true,
    include_worker: false,
    use_postgres: true,
    use_redis: true,
    use_nats: false,
    use_livekit: false,
    isolated_network: false,
  });

  // Load reference data
  useEffect(() => {
    if (isOpen) {
      loadReferenceData();
    }
  }, [isOpen]);

  // Update port preview when category changes
  useEffect(() => {
    if (formData.category) {
      loadPortPreview(formData.category);
    }
  }, [formData.category]);

  async function loadReferenceData() {
    try {
      const [templatesRes, categoriesRes, realmsRes] = await Promise.all([
        fetch("/api/v1/templates"),
        fetch("/api/v1/categories"),
        fetch("/api/v1/realms"),
      ]);

      if (templatesRes.ok) {
        const data = await templatesRes.json();
        setTemplates(data.templates || []);
      }
      if (categoriesRes.ok) {
        setCategories(await categoriesRes.json());
      }
      if (realmsRes.ok) {
        setRealms(await realmsRes.json());
      }
    } catch (e) {
      console.error("Failed to load reference data:", e);
    }
  }

  async function loadPortPreview(category: string) {
    try {
      const res = await fetch(`/api/v1/ports/next-available?category=${category}`);
      if (res.ok) {
        setPortPreview(await res.json());
      }
    } catch (e) {
      console.error("Failed to load port preview:", e);
    }
  }

  async function handleSubmit() {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/v1/projects/scaffold", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to scaffold project");
      }

      const project = await res.json();
      setResult(project);
      setCurrentStep(STEPS.length); // Go to success state
      onSuccess?.(project);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    // Reset state
    setCurrentStep(0);
    setError(null);
    setResult(null);
    setFormData({
      name: "",
      description: "",
      category: "work",
      realm: "midgard",
      template: "ravenmaskos",
      group: "ravenhelm",
      include_api: true,
      include_ui: true,
      include_worker: false,
      use_postgres: true,
      use_redis: true,
      use_nats: false,
      use_livekit: false,
      isolated_network: false,
    });
    onClose();
  }

  function nextStep() {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  }

  function prevStep() {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  }

  function updateFormData(updates: Partial<ScaffoldRequest>) {
    setFormData((prev) => ({ ...prev, ...updates }));
  }

  // Validation
  const isStepValid = () => {
    switch (currentStep) {
      case 0: // Basics
        return formData.name.length >= 2 && formData.name.match(/^[a-z][a-z0-9-]*$/);
      case 1: // Template
        return !!formData.template;
      case 2: // Services
        return formData.include_api || formData.include_ui || formData.include_worker;
      case 3: // Dependencies
        return true;
      case 4: // Review
        return true;
      default:
        return false;
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
        onClick={handleClose}
      />
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 30, stiffness: 300 }}
        className="fixed right-0 top-0 h-full w-full max-w-2xl bg-raven-950 border-l border-raven-800 shadow-2xl z-50 overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-raven-800">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-odin-500/10">
              <Box className="w-6 h-6 text-odin-400" />
            </div>
            <div>
              <h2 className="text-xl font-display font-semibold text-raven-100">
                New Project
              </h2>
              <p className="text-sm text-raven-500">
                Scaffold a new GitLab project with full platform integration
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-raven-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-raven-400" />
          </button>
        </div>

        {/* Progress Steps */}
        {result === null && (
          <div className="px-6 py-4 border-b border-raven-800/50">
            <div className="flex items-center justify-between">
              {STEPS.map((step, index) => (
                <div key={step.id} className="flex items-center">
                  <div
                    className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium transition-colors ${
                      index < currentStep
                        ? "bg-odin-500 text-white"
                        : index === currentStep
                        ? "bg-odin-500/20 text-odin-400 border border-odin-500"
                        : "bg-raven-800 text-raven-500"
                    }`}
                  >
                    {index < currentStep ? (
                      <CheckCircle2 className="w-5 h-5" />
                    ) : (
                      index + 1
                    )}
                  </div>
                  <span
                    className={`ml-2 text-sm ${
                      index <= currentStep ? "text-raven-200" : "text-raven-500"
                    }`}
                  >
                    {step.label}
                  </span>
                  {index < STEPS.length - 1 && (
                    <div
                      className={`w-12 h-0.5 mx-3 ${
                        index < currentStep ? "bg-odin-500" : "bg-raven-800"
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-6 p-4 bg-unhealthy/10 border border-unhealthy/30 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-unhealthy flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-unhealthy font-medium">Error</p>
                <p className="text-sm text-raven-400 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Success State */}
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-12"
            >
              <div className="w-20 h-20 rounded-full bg-healthy/20 flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="w-10 h-10 text-healthy" />
              </div>
              <h3 className="text-2xl font-display font-semibold text-raven-100 mb-2">
                Project Created!
              </h3>
              <p className="text-raven-400 mb-6">
                Your new project <span className="text-odin-400">{result.name}</span> has been scaffolded successfully.
              </p>
              <div className="space-y-3 max-w-md mx-auto text-left">
                <a
                  href={result.gitlab_web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 bg-raven-900 rounded-lg hover:bg-raven-800 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <GitBranch className="w-5 h-5 text-odin-400" />
                    <span className="text-raven-200">GitLab Repository</span>
                  </div>
                  <ExternalLink className="w-4 h-4 text-raven-500" />
                </a>
                <div className="flex items-center justify-between p-4 bg-raven-900 rounded-lg">
                  <div className="flex items-center gap-3">
                    <Globe className="w-5 h-5 text-huginn-400" />
                    <span className="text-raven-200">Domain</span>
                  </div>
                  <code className="text-sm text-raven-400">{result.subdomain}.ravenhelm.test</code>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="mt-8 btn-primary px-8"
              >
                Done
              </button>
            </motion.div>
          )}

          {/* Step Content */}
          {!result && (
            <>
              {/* Step 0: Basics */}
              {currentStep === 0 && (
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-raven-300 mb-2">
                      Project Name *
                    </label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) =>
                        updateFormData({ name: e.target.value.toLowerCase().replace(/\s/g, "-") })
                      }
                      placeholder="my-awesome-project"
                      className="input w-full"
                    />
                    <p className="text-xs text-raven-500 mt-1">
                      Lowercase letters, numbers, and hyphens only
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-raven-300 mb-2">
                      Description
                    </label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => updateFormData({ description: e.target.value })}
                      placeholder="What does this project do?"
                      rows={3}
                      className="input w-full resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-raven-300 mb-2">
                        Category
                      </label>
                      <select
                        value={formData.category}
                        onChange={(e) => updateFormData({ category: e.target.value })}
                        className="input w-full"
                      >
                        {categories.length > 0 ? (
                          categories.map((cat) => (
                            <option key={cat.id} value={cat.id}>
                              {cat.name} ({cat.api_range})
                            </option>
                          ))
                        ) : (
                          <>
                            <option value="platform">Platform</option>
                            <option value="personal">Personal</option>
                            <option value="work">Work</option>
                            <option value="sandbox">Sandbox</option>
                          </>
                        )}
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-raven-300 mb-2">
                        Realm (Environment)
                      </label>
                      <select
                        value={formData.realm}
                        onChange={(e) => updateFormData({ realm: e.target.value })}
                        className="input w-full"
                      >
                        {realms.length > 0 ? (
                          realms.slice(0, 3).map((realm) => (
                            <option key={realm.id} value={realm.id}>
                              {realm.name}
                            </option>
                          ))
                        ) : (
                          <>
                            <option value="midgard">Midgard (Development)</option>
                            <option value="alfheim">Alfheim (Staging)</option>
                            <option value="asgard">Asgard (Production)</option>
                          </>
                        )}
                      </select>
                    </div>
                  </div>

                  {portPreview && (
                    <div className="p-4 bg-raven-900 rounded-lg">
                      <p className="text-sm text-raven-400 mb-2">Port Preview</p>
                      <div className="flex gap-4">
                        <div className="flex items-center gap-2">
                          <Server className="w-4 h-4 text-odin-400" />
                          <span className="text-raven-300">API: {portPreview.api_port}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Globe className="w-4 h-4 text-huginn-400" />
                          <span className="text-raven-300">UI: {portPreview.ui_port}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Step 1: Template */}
              {currentStep === 1 && (
                <div className="space-y-4">
                  <p className="text-raven-400 mb-4">
                    Choose a template to bootstrap your project structure.
                  </p>
                  {templates.length > 0 ? (
                    templates.map((template) => (
                      <button
                        key={template.id}
                        onClick={() => updateFormData({ template: template.id })}
                        className={`w-full p-4 text-left rounded-lg border transition-colors ${
                          formData.template === template.id
                            ? "border-odin-500 bg-odin-500/10"
                            : "border-raven-800 bg-raven-900 hover:border-raven-700"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-medium text-raven-100">{template.name}</h4>
                            <p className="text-sm text-raven-400 mt-1">{template.description}</p>
                            <div className="flex flex-wrap gap-2 mt-3">
                              {template.features.slice(0, 4).map((feature, i) => (
                                <span key={i} className="text-xs px-2 py-1 bg-raven-800 rounded text-raven-400">
                                  {feature}
                                </span>
                              ))}
                            </div>
                          </div>
                          {formData.template === template.id && (
                            <CheckCircle2 className="w-5 h-5 text-odin-400 flex-shrink-0" />
                          )}
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="space-y-4">
                      <button
                        onClick={() => updateFormData({ template: "ravenmaskos" })}
                        className={`w-full p-4 text-left rounded-lg border transition-colors ${
                          formData.template === "ravenmaskos"
                            ? "border-odin-500 bg-odin-500/10"
                            : "border-raven-800 bg-raven-900 hover:border-raven-700"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Code2 className="w-6 h-6 text-odin-400" />
                            <div>
                              <h4 className="font-medium text-raven-100">RavenmaskOS</h4>
                              <p className="text-sm text-raven-400">Full-stack FastAPI + Next.js</p>
                            </div>
                          </div>
                          {formData.template === "ravenmaskos" && (
                            <CheckCircle2 className="w-5 h-5 text-odin-400" />
                          )}
                        </div>
                      </button>
                      <button
                        onClick={() => updateFormData({ template: "platform-template" })}
                        className={`w-full p-4 text-left rounded-lg border transition-colors ${
                          formData.template === "platform-template"
                            ? "border-odin-500 bg-odin-500/10"
                            : "border-raven-800 bg-raven-900 hover:border-raven-700"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Layers className="w-6 h-6 text-huginn-400" />
                            <div>
                              <h4 className="font-medium text-raven-100">Platform Template</h4>
                              <p className="text-sm text-raven-400">CI/CD + Terraform infrastructure</p>
                            </div>
                          </div>
                          {formData.template === "platform-template" && (
                            <CheckCircle2 className="w-5 h-5 text-odin-400" />
                          )}
                        </div>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Step 2: Services */}
              {currentStep === 2 && (
                <div className="space-y-6">
                  <p className="text-raven-400">
                    Select which services to include in your project.
                  </p>
                  <div className="space-y-3">
                    <ServiceToggle
                      label="API Backend"
                      description="FastAPI backend service"
                      icon={Server}
                      checked={formData.include_api}
                      onChange={(checked) => updateFormData({ include_api: checked })}
                    />
                    <ServiceToggle
                      label="UI Frontend"
                      description="Next.js frontend application"
                      icon={Globe}
                      checked={formData.include_ui}
                      onChange={(checked) => updateFormData({ include_ui: checked })}
                    />
                    <ServiceToggle
                      label="Background Worker"
                      description="Async task processing"
                      icon={Box}
                      checked={formData.include_worker}
                      onChange={(checked) => updateFormData({ include_worker: checked })}
                    />
                  </div>
                </div>
              )}

              {/* Step 3: Dependencies */}
              {currentStep === 3 && (
                <div className="space-y-6">
                  <p className="text-raven-400">
                    Select shared platform services your project needs.
                  </p>
                  <div className="space-y-3">
                    <ServiceToggle
                      label="PostgreSQL Database"
                      description="Shared database with pgvector"
                      icon={Database}
                      checked={formData.use_postgres}
                      onChange={(checked) => updateFormData({ use_postgres: checked })}
                    />
                    <ServiceToggle
                      label="Redis Cache"
                      description="Caching and sessions"
                      icon={Database}
                      checked={formData.use_redis}
                      onChange={(checked) => updateFormData({ use_redis: checked })}
                    />
                    <ServiceToggle
                      label="NATS Messaging"
                      description="Real-time event messaging"
                      icon={Network}
                      checked={formData.use_nats}
                      onChange={(checked) => updateFormData({ use_nats: checked })}
                    />
                    <ServiceToggle
                      label="LiveKit WebRTC"
                      description="Voice and video capabilities"
                      icon={Network}
                      checked={formData.use_livekit}
                      onChange={(checked) => updateFormData({ use_livekit: checked })}
                    />
                  </div>
                  <div className="pt-4 border-t border-raven-800">
                    <ServiceToggle
                      label="Isolated Network"
                      description="Create a separate Docker network for this project"
                      icon={Network}
                      checked={formData.isolated_network}
                      onChange={(checked) => updateFormData({ isolated_network: checked })}
                    />
                  </div>
                </div>
              )}

              {/* Step 4: Review */}
              {currentStep === 4 && (
                <div className="space-y-6">
                  <p className="text-raven-400 mb-4">
                    Review your project configuration before creating.
                  </p>
                  
                  <div className="space-y-4">
                    <ReviewSection title="Project Details">
                      <ReviewItem label="Name" value={formData.name} />
                      <ReviewItem label="Category" value={formData.category} />
                      <ReviewItem label="Realm" value={formData.realm} />
                      <ReviewItem label="Template" value={formData.template} />
                    </ReviewSection>

                    <ReviewSection title="Services">
                      <ReviewItem 
                        label="Included" 
                        value={[
                          formData.include_api && "API",
                          formData.include_ui && "UI",
                          formData.include_worker && "Worker",
                        ].filter(Boolean).join(", ") || "None"}
                      />
                    </ReviewSection>

                    <ReviewSection title="Dependencies">
                      <ReviewItem 
                        label="Shared Services" 
                        value={[
                          formData.use_postgres && "PostgreSQL",
                          formData.use_redis && "Redis",
                          formData.use_nats && "NATS",
                          formData.use_livekit && "LiveKit",
                        ].filter(Boolean).join(", ") || "None"}
                      />
                      <ReviewItem 
                        label="Network" 
                        value={formData.isolated_network ? "Isolated" : "Shared (platform_net)"}
                      />
                    </ReviewSection>

                    {portPreview && (
                      <ReviewSection title="Port Allocation">
                        <ReviewItem label="API Port" value={portPreview.api_port.toString()} />
                        <ReviewItem label="UI Port" value={portPreview.ui_port.toString()} />
                      </ReviewSection>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!result && (
          <div className="flex items-center justify-between p-6 border-t border-raven-800">
            <button
              onClick={prevStep}
              disabled={currentStep === 0}
              className="btn-secondary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
              Back
            </button>
            
            {currentStep < STEPS.length - 1 ? (
              <button
                onClick={nextStep}
                disabled={!isStepValid()}
                className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={loading || !isStepValid()}
                className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Create Project
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}

// Helper Components
function ServiceToggle({
  label,
  description,
  icon: Icon,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  icon: any;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`w-full p-4 text-left rounded-lg border transition-colors ${
        checked
          ? "border-odin-500/50 bg-odin-500/10"
          : "border-raven-800 bg-raven-900 hover:border-raven-700"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Icon className={`w-5 h-5 ${checked ? "text-odin-400" : "text-raven-500"}`} />
          <div>
            <h4 className={`font-medium ${checked ? "text-raven-100" : "text-raven-300"}`}>
              {label}
            </h4>
            <p className="text-sm text-raven-500">{description}</p>
          </div>
        </div>
        <div
          className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
            checked
              ? "border-odin-500 bg-odin-500"
              : "border-raven-600"
          }`}
        >
          {checked && <CheckCircle2 className="w-3 h-3 text-white" />}
        </div>
      </div>
    </button>
  );
}

function ReviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-raven-900 rounded-lg p-4">
      <h4 className="text-sm font-medium text-raven-400 mb-3">{title}</h4>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-raven-500">{label}</span>
      <span className="text-raven-200">{value}</span>
    </div>
  );
}

