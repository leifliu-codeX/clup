import{g as t}from"./vendor.194c4086.js";const r=(t,r)=>{var e,o=null;return function(){let n=this,s=arguments;return o&&clearTimeout(o),o=setTimeout((function(){o=null,e=t.apply(n,s)}),r),e}},e=(r,e="success",o=2e3,n=!1,s=!0,a=!1)=>{t.exports.Message({message:r,type:e,duration:o,center:n,showClose:s,dangerouslyUseHTMLString:a})};function o(r,e,o="success",n=!1){t.exports.Notification({title:r,message:e,type:o,dangerouslyUseHTMLString:n,duration:2500})}const n=(r,e=window.vm.$t("Public.ping-ming-jia-zai-zhong"),o=!0)=>t.exports.Loading.service({target:document.querySelector(r),text:e,lock:o}),s=t=>{if(isNaN(Number(t)))return t;if(0===t)return"0 B";const r=Math.floor(Math.log(t)/Math.log(1024));return`${(t/Math.pow(1024,r)).toFixed(2)} ${["B","KB","MB","GB","TB","PB"][r]}`},a=t=>{const r=t.match(/([\d.]+)\s*([a-zA-Z]+)/);if(r){return{value:parseFloat(r[1]),unit:r[2]}}throw new Error("请检查传入信息是否准确")},i=(t,r="")=>{let e;if("string"==typeof t)e=t;else{if("number"!=typeof t)throw new Error("请检查传入信息是否准确");e=t+r}const o=e.match(/([\d.]+)\s*([a-zA-Z]+)/);if(o){const t=parseFloat(o[1]),r=o[2],e=1024;let n=["MB","GB","TB","PB"].findIndex((t=>t===r));if(-1===n)throw new Error("请检查传入信息是否准确");return t*Math.pow(e,n)}throw new Error("请检查传入信息是否准确")},u=t=>{if(isNaN(t))throw new Error("请检查传入信息是否准确");if(0===t)throw new Error("请检查传入信息是否准确");let r=Math.floor(Math.log(t)/Math.log(1024));return{value:Math.floor(t/Math.pow(1024,r)),unit:["MB","GB","TB","PB"][r]}};export{n as a,a as b,s as c,r as d,u as f,i as g,e as s,o as t};
