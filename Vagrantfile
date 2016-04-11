# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  # All Vagrant configuration is done here. The most common configuration
  # options are documented and commented below. For a complete reference,
  # please see the online documentation at vagrantup.com.

  # Every Vagrant virtual environment requires a box to build off of.
  config.vm.box = "trusty64-vanilla"
  config.vm.box_url = "https://dl.dropboxusercontent.com/u/11847976/trusty64-vanilla.box"

  config.vm.synced_folder ENV["FO_OPS_DIR"], ::File.join("", "ops")

  # download the chef bootstrap file if it doesn't already exist
  require 'tmpdir'
  chef_bootstrap = ::File.join(::Dir.tmpdir, "chef-bootstrap.sh")
  if !::File.exists?(chef_bootstrap)
    require 'open-uri'
    download = open('https://raw.githubusercontent.com/Jaymon/vagrant-bootstrap/master/chef-bootstrap.sh')
    ::IO.copy_stream(download, chef_bootstrap)
  end
  config.vm.provision :shell, :path => chef_bootstrap

  config.vm.provision :chef_solo do |chef|
    chef.cookbooks_path = ::File.join(ENV["FO_OPS_DIR"], "chef", "cookbooks")
    #chef.roles_path = "../my-recipes/roles"
    #chef.data_bags_path = "../my-recipes/data_bags"


#     chef.add_recipe "locations"
#     chef.json = {
# 
#       "locations" => {
#         "users" => {
#           "vagrant" => {
#             "home_index" => {
#               "src" => "/vagrant",
#               "dest" => "/tmp/vagrant/locations/test",
#               "mode" => "0777"
#             }
#           },
#         },
#       },
# 
#     }

    chef.add_recipe "package::update"
    chef.add_recipe "package"
    chef.add_recipe "pip"
    chef.add_recipe "environ"
    chef.add_recipe "environ::python"

    #chef.add_role ""

    # You may also specify custom JSON attributes:
    chef.json = {
      "package" => {
        :install => [
          "python-dev",
          "git",
        ]
      },
      "pip" => {
        :install => [
          "pout", #"git+https://github.com/Jaymon/pout#egg=pout",
          "testdata", #"git+https://github.com/Jaymon/testdata#egg=testdata",
          "pyt", #"git+https://github.com/Jaymon/pyt#egg=pyt",
          "git+https://github.com/firstopinion/captain#egg=captain==0.4.1",
          "geoip2",
        ],
        :upgrade => [],
      },
      "environ" => {
        "global" => {
          :set => {
          }
        },
        "python" => {
          #"sitecustomize" => ::File.join("", "ops", "conf", "sitecustomize.py")
          "usercustomize" => {
            "vagrant" => ::File.join("", "ops", "conf", "sitecustomize.py"),
            "root" => ::File.join("", "ops", "conf", "sitecustomize.py")
          }
        }
      },
      }

  end

end
