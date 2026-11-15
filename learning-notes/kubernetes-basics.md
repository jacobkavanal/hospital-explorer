# Kubernetes and NRP: learning notes

## Kubernetes

- Kubernetes manages programs running in containers across a cluster of machines.
- NRP's Nautilus cluster uses Kubernetes to run research workloads.
- `kubectl` is the command-line tool used to communicate with Kubernetes.
- Having `kubectl` installed does not give me permission to use NRP. I still need authentication and access to the team's namespace.

## Namespace

- A namespace groups a team's resources inside the shared cluster.
- Resources include Jobs, Pods and persistent storage requests.
- My mentor is arranging our project namespace and membership.
- Access depends on permissions. Joining our namespace does not automatically allow me to modify another team's jobs.

## Container

- A container packages a program and its dependencies so it can run in a consistent environment.
- For our project, it could contain Python, the required libraries and the hospital refresh code.

## Pod

- A Pod is the Kubernetes unit that runs one or more containers.
- Our simple refresh would use one application container in a Pod.
- Pods are temporary. They can finish, fail or be replaced.
- Files stored only in a container's temporary filesystem should not be relied on after the Pod is removed.

## Job

- A Job tells Kubernetes to run a task to completion.
- It creates a Pod to run the program and tracks whether the task succeeds.
- Depending on its settings, it can retry failed work by creating another Pod.
- A Job fits our refresh because fetching, cleaning and saving data has a clear endpoint.
- A Job is not inherently less compute-intensive. Once its Pod finishes, the program stops consuming compute rather than remaining active continuously.
- A Job does not itself mean “run daily.” A recurring schedule is a separate concern.

## Persistent storage

- Persistent storage keeps files beyond the life of an individual Pod.
- A PersistentVolumeClaim, or PVC, requests storage for a workload.
- Kubernetes connects the claim to a PersistentVolume, or PV, that provides the storage.
- The Pod mounts that storage as a folder that the program can read and write.
- Saving `hospital.sqlite` in that mounted folder lets it survive removal of the Pod.
- Persistent does not mean permanent or backed up. Deleting storage resources can still remove data, depending on the storage policy.

## How the pieces fit together

Example: refreshing hospital data on NRP.

1. Our namespace contains the Job and its storage claim.
2. The Job creates a Pod.
3. The Pod runs a container containing the refresh program.
4. The program fetches and cleans hospital data.
5. It saves the database to a folder mounted from persistent storage.
6. The program exits and the Job records completion.
7. The Pod can be removed while the saved database remains on the persistent storage.

The namespace organizes the work. The Job manages completion. The Pod runs the container. The mounted storage preserves the output.

This describes a possible NRP deployment of our hospital refresh. We have not run this workload on NRP yet.

## What I have done so far

- Verified that `kubectl` is installed and runs on my Mac.
- Ran `kubectl version --client`, which checks the local tool without connecting to NRP.
- Ran `kubectl config get-contexts` and received only the header, meaning no saved cluster contexts were configured at that point.
- Signed in to the NRP portal through UCSD.
- Learned how namespaces, Jobs, Pods and persistent storage relate.
- Project namespace membership has not yet been confirmed.

A context is a saved connection setup identifying a cluster, a user and optionally a default namespace. Signing in through the website does not by itself configure a local `kubectl` context.

## Useful commands

```bash
# Check the local client without contacting a cluster
kubectl version --client

# List locally saved connection contexts
kubectl config get-contexts
```

## Reference

- [NRP getting-started guide](https://nrp.ai/documentation/userdocs/start/getting-started/)
