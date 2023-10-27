#############################################################################
# Demonstrates displaying a VM's current snapshot, then cloning a VM        #
# to a different datastore. The customer request is to be able to clone a   #
# VM to a separate datastore for their forensics department to review       #
# Most of the code here is taken from samples available at                  #
#  https://github.com/vmware/pyvmomi-community-samples/tree/master/samples  #
#############################################################################

from pyVmomi import vim
from pyVim.connect import SmartConnect

import pchelper

import os
import ssl

def get_current_snap_obj(snapshots, snapob):
    snap_obj = []
    for snapshot in snapshots:
        if snapshot.snapshot == snapob:
            snap_obj.append(snapshot)
        snap_obj = snap_obj + get_current_snap_obj(
                                snapshot.childSnapshotList, snapob)
    return snap_obj

def wait_for_task(task):
    """ wait for a vCenter task to finish """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            print("there was an error")
            print(task.info.error)
            task_done = True

def clone_vm(
        content, template, vm_name, datacenter_name, vm_folder, datastore_name,
        cluster_name, resource_pool, power_on, datastorecluster_name):
    """
    Clone a VM from a template/VM, datacenter_name, vm_folder, datastore_name
    cluster_name, resource_pool, and power_on are all optional.
    """

    # if none git the first one
    datacenter = pchelper.get_obj(content, [vim.Datacenter], datacenter_name)

    if vm_folder:
        destfolder = pchelper.search_for_obj(content, [vim.Folder], vm_folder)
    else:
        destfolder = datacenter.vmFolder

    if datastore_name:
        datastore = pchelper.search_for_obj(content, [vim.Datastore], datastore_name)
    else:
        datastore = pchelper.get_obj(
            content, [vim.Datastore], template.datastore[0].info.name)

    # if None, get the first one
    cluster = pchelper.search_for_obj(content, [vim.ClusterComputeResource], cluster_name)
    if not cluster:
        clusters = pchelper.get_all_obj(content, [vim.ResourcePool])
        cluster = list(clusters)[0]

    if resource_pool:
        resource_pool = pchelper.search_for_obj(content, [vim.ResourcePool], resource_pool)
    else:
        resource_pool = cluster.resourcePool

    vmconf = vim.vm.ConfigSpec()

    if datastorecluster_name:
        podsel = vim.storageDrs.PodSelectionSpec()
        pod = pchelper.get_obj(content, [vim.StoragePod], datastorecluster_name)
        podsel.storagePod = pod

        storagespec = vim.storageDrs.StoragePlacementSpec()
        storagespec.podSelectionSpec = podsel
        storagespec.type = 'create'
        storagespec.folder = destfolder
        storagespec.resourcePool = resource_pool
        storagespec.configSpec = vmconf

        try:
            rec = content.storageResourceManager.RecommendDatastores(
                storageSpec=storagespec)
            rec_action = rec.recommendations[0].action[0]
            real_datastore_name = rec_action.destination.name
        except Exception:
            real_datastore_name = template.datastore[0].info.name

        datastore = pchelper.get_obj(content, [vim.Datastore], real_datastore_name)

    # set relospec
    relospec = vim.vm.RelocateSpec()
    relospec.datastore = datastore
    relospec.pool = resource_pool

    clonespec = vim.vm.CloneSpec()
    clonespec.location = relospec
    clonespec.powerOn = power_on

    task = template.Clone(folder=destfolder, name=vm_name, spec=clonespec)
    wait_for_task(task)
    print("VM cloned.")    

def main():
    DEBUG=False

    s=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    s.check_hostname = False
    s.load_default_certs()
    s.verify_mode=ssl.CERT_REQUIRED
    vc = os.getenv('vc_url')
    vc_username = os.getenv('vc_username')
    vc_password = os.getenv('vc_password')
    if DEBUG: print(f"vCenter: {vc}, Username: {vc_username}, Password: {vc_password}")

    vm_name = "kremerpt-tc1"
    datacenter_name = "SDDC-Datacenter"
    vm_folder = "Workloads"
    datastore_name = "ds01"
    cluster_name = "Cluster-1"
    resource_pool = "Compute-ResourcePool"

    si=SmartConnect(host=vc, user=vc_username, pwd=vc_password,sslContext=s)

    #vm_list = pchelper.get_all_obj(si.content,[vim.VirtualMachine])
    #print(vm_list)

    vm = pchelper.get_obj(si.content,[vim.VirtualMachine],vm_name)
    if vm.snapshot:
        current_snapref = vm.snapshot.currentSnapshot
        current_snap_obj = get_current_snap_obj(
                            vm.snapshot.rootSnapshotList, current_snapref)        
        current_snapshot = "Name: %s; Description: %s; " \
                           "CreateTime: %s; State: %s" % (
                                current_snap_obj[0].name,
                                current_snap_obj[0].description,
                                current_snap_obj[0].createTime,
                                current_snap_obj[0].state)
        print("Virtual machine %s current snapshot is:" % vm.name)
        print(current_snapshot)

        clone_name = (vm.name + "-clone")
        print(f"Cloning {vm_name} to {clone_name}")
        value = input("Continue with clone? Y/N: ")
        if value == "Y" or value == "y":
            clone_vm(si.content,vm,clone_name,datacenter_name,vm_folder,datastore_name,cluster_name, resource_pool,False,None)
    else:
        print(f"{vm.name} has no snapshots")
        return


if __name__ == "__main__":
    main()