import{A as s}from"./api_clusterManage.788b7961.js";import{i as a}from"./verificationRules.bef90446.js";import{d as e,s as t,t as i}from"./staticTools.84335405.js";import{n as r}from"./index.e4a37cdc.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";var o=function(){var s=this,a=s.$createElement,e=s._self._c||a;return e("el-form",{directives:[{name:"loading",rawName:"v-loading",value:s.pfsDiskNmaeFromLoading,expression:"pfsDiskNmaeFromLoading"}],ref:"pfsDiskNmaeFrom",attrs:{"element-loading-text":s.$t("Public.ping-ming-jia-zai-zhong"),model:s.pfsDiskNmaeFrom,"label-width":"180px",rules:s.pfsDiskNmaeRules}},[e("el-row",{staticStyle:{display:"flex","align-items":"center"}},[e("el-col",{staticClass:"prefix_style",attrs:{span:12}},[e("el-form-item",{attrs:{label:"pfs_disk_name",prop:"pfs_disk_name"}},[e("el-input",{staticStyle:{"margin-top":"6px"},attrs:{placeholder:s.$t("createPolardbCluster.qingshuru-pfs_disk_name")},on:{input:s.diskNameInput},model:{value:s.pfsDiskNmaeFrom.pfs_disk_name,callback:function(a){s.$set(s.pfsDiskNmaeFrom,"pfs_disk_name",a)},expression:"pfsDiskNmaeFrom.pfs_disk_name"}},[e("template",{slot:"prepend"},[s._v("/dev/")]),e("el-button",{staticStyle:{"font-size":"12px"},attrs:{slot:"append",icon:"iconfont el-icon-jiance"},on:{click:s.inspectionDiskName},slot:"append"},[s._v(s._s(s.$t("createPolardbCluster.jian-ce")))])],2)],1)],1),-1==s.pfsDIskNmaeStep?e("el-col",{attrs:{span:12}},[e("el-form-item",{attrs:{"label-width":"20px"}},[e("el-tag",{attrs:{type:"warning"}},[s._v(s._s(s.$t("createPolardbCluster.cipanmingcheng-jiance-m")))])],1)],1):e("el-col",{attrs:{span:12}},[e("el-form-item",{attrs:{"label-width":"20px"}},[e("el-tag",{attrs:{type:"warning"}},[s._v(s._s(s.$t("createPolardbCluster.zaicigenggai-cipanming-m")))])],1)],1)],1),1==s.pfsDIskNmaeStep?e("el-row",[e("el-col",{attrs:{span:12}},[e("el-form-item",{attrs:{label:"polar_datadir",prop:"polar_datadir"}},[e("el-input",{attrs:{placeholder:s.$t("createPolardbCluster.qingshuru-polar_datadir")},on:{blur:function(a){s.pfsDiskNmaeFrom.polar_datadir=a.target.value.trim()}},model:{value:s.pfsDiskNmaeFrom.polar_datadir,callback:function(a){s.$set(s.pfsDiskNmaeFrom,"polar_datadir",a)},expression:"pfsDiskNmaeFrom.polar_datadir"}})],1)],1),e("el-col",{attrs:{span:12}},[e("el-form-item",{attrs:{label:"pfsdaemon_params",prop:"pfsdaemon_params"}},[e("el-input",{attrs:{placeholder:s.$t("createPolardbCluster.qingshuru-pfsdaemon_parms")},on:{blur:function(a){s.pfsDiskNmaeFrom.pfsdaemon_params=a.target.value.trim()}},model:{value:s.pfsDiskNmaeFrom.pfsdaemon_params,callback:function(a){s.$set(s.pfsDiskNmaeFrom,"pfsdaemon_params",a)},expression:"pfsDiskNmaeFrom.pfsdaemon_params"}})],1)],1),e("el-col",{attrs:{span:24}},[e("el-form-item",{attrs:{label:"",prop:""}},[e("span",{staticStyle:{"font-size":"14px"}},[s._v(s._s(s.$t("createPolardbCluster.qingdianji-geshihuaanniu-m"))),e("span",{staticStyle:{color:"red"}},[s._v(s._s(s.$t("createPolardbCluster.geshihua-jiangshi-m")))]),s._v("）")]),e("el-button",{class:{greenBtn:s.isFormat},staticStyle:{"margin-top":"12px"},attrs:{type:"primary",loading:s.formatLoading,icon:"iconfont el-icon-geshihua"},on:{click:s.formatDisk}},[s._v(s._s(s.$t("createPolardbCluster.ge-shi-hua")))])],1)],1)],1):s._e(),e("span",{staticStyle:{display:"block",color:"red","font-size":"14px","margin-left":"60px","text-align":"left"}},[s._v(s._s(s.showmessage))])],1)},n=[];const m={data(){return{pfsDiskNmaeFrom:{},pfsDiskNmaeRules:{pfs_disk_name:[{required:!0,message:this.$t("createPolardbCluster.qingshuru-pfs_disk_name"),trigger:"blur"},{required:!0,validator:a}],polar_datadir:[{required:!0,message:this.$t("createPolardbCluster.qingshuru-polar_datadir"),trigger:"blur"}]},pfsDIskNmaeStep:-1,pfsDiskNmaeFromLoading:!1,formatLoading:!1,isFormat:!1,databaseDeploymentForm:{},showmessage:""}},watch:{isFormat:{handler(s,a){this.$emit("isFormat",s)}}},methods:{diskNameInput:e((function(...s){this.diskNameInputFunc(...s)}),240),diskNameInputFunc(s){const a=this;a.pfsDIskNmaeStep=-1,a.pfsDiskNmaeFrom={pfs_disk_name:s,pfsdaemon_params:"-w 2",polar_datadir:"shared_data"},a.isFormat=!1},inspectionDiskName(){const a=this;a.diskNameInputFunc(a.pfsDiskNmaeFrom.pfs_disk_name),this.$nextTick((()=>{a.$refs.pfsDiskNmaeFrom.validate((e=>{if(e){let e={pfs_disk_name:a.pfsDiskNmaeFrom.pfs_disk_name,host_list:[a.databaseDeploymentForm.host]};a.pfsDiskNmaeFromLoading=!0,a.isTesting=!0,s.checkPfsDiskNameValidity(e).then((s=>{s.is_valid?(a.showmessage="",a.pfsDIskNmaeStep=1,a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1,!0===s.formated&&(a.isFormat=!0,t(a.$t("createPolardbCluster.cipan-yijing-geshihua-next-m")))):(a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1,a.$alert(s.err_msg,a.$t("createPolardbCluster.cipanjiance-yichang-m"),{confirmButtonText:a.$t("createDatabasePage.wozhidaole"),type:"error"}),a.showmessage=s.err_msg)})).catch((()=>{a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1}))}}))}))},formatDisk(){const a=this;let e=(!0===a.isFormat?a.$t("createPolardbCluster.cipan-yijing-geshihua-question-m"):"")+a.$t("createPolardbCluster.geshihua-jiangshi-m-t"),t=!0===a.isFormat?a.$t("dbList.shi"):a.$t("dynamicTools.que-ren"),r=a.isFormat?a.$t("dbList.fou"):a.$t("dynamicTools.qu-xiao");a.$confirm(e,a.$t("polarDbEditDBList.jing-gao"),{confirmButtonText:t,cancelButtonText:r,type:"warning",iconClass:"el-icon-warning",dangerouslyUseHTMLString:!0}).then((()=>{a.formatLoading=!0,a.pfsDiskNmaeFromLoading=!0,a.isTesting=!0;let e={pfs_disk_name:a.pfsDiskNmaeFrom.pfs_disk_name,host_list:[a.databaseDeploymentForm.host]};s.formatPfsDisk(e).then((s=>{i(a.$t("createPolardbCluster.geshihua-chenggong"),"success"),a.isFormat=!0,a.formatLoading=!1,a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1}),(s=>{a.isFormat=!1,a.formatLoading=!1,a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1}))})).catch((()=>{a.formatLoading=!1,a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1}))},successNextStep(){const a=this;this.$refs.pfsDiskNmaeFrom.validate((e=>{if(e){let e={host:a.databaseDeploymentForm.host,pfs_disk_name:a.pfsDiskNmaeFrom.pfs_disk_name,polar_datadir:a.pfsDiskNmaeFrom.polar_datadir};a.isTesting=!0,a.isTestingLoading=!0,a.pfsDiskNmaeFromLoading=!0,s.checkPolarSharedDirs(e).then((function(s){a.pfsDiskNmaeFromLoading=!1,a.isTesting=!1,a.isTestingLoading=!1,0==s.err_code?(a.showmessage="",a.$emit("success",a.pfsDiskNmaeFrom)):a.showmessage=s.err_msg}),(function(s){a.isTesting=!1,a.isTestingLoading=!1,a.pfsDiskNmaeFromLoading=!1}))}}))},firstNextStep(s){this.databaseDeploymentForm=JSON.parse(JSON.stringify(s)),this.isFormat=!1,this.pfsDIskNmaeStep=-1}}},l={};var p=r(m,o,n,!1,d,null,null,null);function d(s){for(let a in l)this[a]=l[a]}var f=function(){return p.exports}();export{f as default};