# Azure Foundry Agent - Setup Instructions

## Prerequisites

- Python 3.12+
- An Azure subscription
- Access to Azure AI Foundry

## Step 1: Install Required Packages

```bash
python -m pip install --pre "azure-ai-projects>=2.0.0b1"
python -m pip install python-dotenv
```

> **Note:** Use `python -m pip` instead of bare `pip` to avoid issues with stale pip installations pointing to removed Python versions.

## Step 2: Create an App Registration in Azure

1. Go to the [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** (formerly Azure Active Directory)
3. Go to **App registrations** → **+ New registration**
4. Give it a name (e.g., "MyFoundryAgent") and click **Register**
5. On the app's **Overview** page, note down:
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`

## Step 3: Create a Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **+ New client secret**
3. Add a description and choose an expiry period
4. Click **Add** and **immediately copy the Value** (it's only shown once) → `AZURE_CLIENT_SECRET`

## Step 4: Get Your Azure AI Foundry Endpoint

1. Go to [Azure AI Foundry](https://ai.azure.com)
2. Open your project
3. Find the project endpoint URL → `AZURE_ENDPOINT`

## Step 5: Deploy a Model

1. In Azure AI Foundry, open your project
2. Go to **Deployments** → **+ Deploy model** → **Deploy base model**
3. Select your model (e.g., `gpt-4o-mini` for a cost-effective option)
4. Deploy and note the **deployment name** → `MODEL_DEPLOYMENT_NAME`

## Step 6: Assign Roles to the Service Principal

Your app registration (service principal) needs permissions on **two** resources.

### On the AI Services Resource:

1. In the Azure Portal, navigate to your **Azure AI Services** resource
2. Go to **Access control (IAM)** → **+ Add** → **Add role assignment**
3. Select the **Azure AI User** role → **Next**
4. Under Members, select **User, group, or service principal**
5. Click **+ Select members** and search for your app registration by its **client ID**
6. Select it → **Review + assign**

### On the AI Foundry Project (Machine Learning Workspace):

1. In the Azure Portal, navigate to your **Azure AI project** (Machine Learning workspace)
2. Go to **Access control (IAM)** → **+ Add** → **Add role assignment**
3. Select the **Azure AI User** role → **Next**
4. Under Members, select **User, group, or service principal**
5. Search for your app registration by its **client ID**
6. Select it → **Review + assign**

> **Important:** Role assignments can take 1-5 minutes to propagate. If you get a `PermissionDenied` error, wait a few minutes and retry.

## Step 7: Configure Environment Variables

Create a `.env` file in your project root:

```env
AZURE_ENDPOINT=<your-project-endpoint>
MODEL_DEPLOYMENT_NAME=<your-model-deployment-name>
AZURE_CLIENT_ID=<your-client-id>
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_SECRET=<your-client-secret>
```

> **Important:** Add `.env` to your `.gitignore` to avoid committing secrets.

## Step 8: Run the Agent

```bash
python azureFoundry.py
```

You should see output like:

```
Response output: Under the ancient oak tree, she found an old locket that whispered secrets of love lost and time forgotten.
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| `PermissionDenied: lacks required data action` | Assign **Azure AI User** role to your service principal on both the AI Services resource and the AI project |
| `DeploymentNotFound` | Deploy the model in Azure AI Foundry portal under Deployments |
| `DefaultAzureCredential failed` | Ensure `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_CLIENT_SECRET` are set in your `.env` file |
| `pip: Unable to create process` | Use `python -m pip` instead of bare `pip` |
