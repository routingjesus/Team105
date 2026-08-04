import { DatasetWizard } from "@/components/wizard/dataset-wizard";

export const metadata = {
  title: "New dataset — Team105 Dataset Creation Wizard",
};

export default function NewDatasetPage() {
  return (
    <div className="wizard-page">
      <h1>Create a dataset</h1>
      <DatasetWizard />
    </div>
  );
}
